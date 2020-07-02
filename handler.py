import os
import sys
import json
import uuid
import logging

import six
from oslo_config import cfg
from stevedore.driver import DriverManager
from six.moves.urllib.parse import parse_qsl

from st2common.bootstrap.actionsregistrar import ActionsRegistrar
from st2common.constants.action import LIVEACTION_STATUS_SUCCEEDED
from st2common.constants.pack import CONFIG_SCHEMA_FILE_NAME
from st2common.constants.system import VERSION_STRING
from st2common.content.loader import ContentPackLoader, MetaLoader
from st2common.content import utils as content_utils
from st2common.exceptions import actionrunner
from st2common.exceptions.param import ParamException
from st2common.models.api.action import ActionAPI, RunnerTypeAPI
from st2common.models.api.pack import ConfigSchemaAPI
from st2common.runners.base import ActionRunner
from st2common.util.pack import validate_config_against_schema
from st2common.util import param as param_utils

del sys.argv[1:]

cfg.CONF(args=('--config-file', 'st2.conf'), version=VERSION_STRING)

LOG = logging.getLogger(__name__)
logging.basicConfig()

def _load_actions():
    actions = {}
    action_dirs = ContentPackLoader().get_content(content_utils.get_packs_base_paths(), 'actions')

    for pack in action_dirs:
        for action_path in ActionsRegistrar().get_resources_from_pack(action_dirs[pack]):
            content = MetaLoader().load(action_path)
            ref = pack + "." + content['name']

            action_api = ActionAPI(pack=pack, **content)
            action_api.validate()
            # action_validator.validate_action(action_api)
            actions[ref] = ActionAPI.to_model(action_api)

    return actions


def _load_config_schemas():
    config_schemas = {}

    packs = ContentPackLoader().get_packs(content_utils.get_packs_base_paths())

    for pack_name, pack_dir in six.iteritems(packs):
        config_schema_path = os.path.join(pack_dir, CONFIG_SCHEMA_FILE_NAME)

        if not os.path.isfile(config_schema_path):
            # Note: Config schema is optional
            continue

        values = MetaLoader().load(config_schema_path)

        if not values:
            raise ValueError('Config schema "%s" is empty and invalid.' % (config_schema_path))

        content = {}
        content['pack'] = pack_name
        content['attributes'] = values

        config_schema_api = ConfigSchemaAPI(**content)
        config_schema_api = config_schema_api.validate()
        config_schemas[pack_name] = values

    return config_schemas

ACTIONS = _load_actions()
CONFIG_SCHEMAS = _load_config_schemas()

def main():
    # Read DEBUG value from the environment variable
    debug = os.environ.get('ST2_DEBUG', False)
    if str(debug).lower() in ['true', '1']:
        debug = True

    if debug:
        LOG.setLevel(logging.DEBUG)
    else:
        LOG.setLevel(logging.INFO)

    # Read
    input = os.environ.get('ST2_INPUT', {})
    if isinstance(input, six.string_types):
        try:
            input = json.loads(input)
        except ValueError as e:
            LOG.error("ERROR: Can not parse `input`: '{}'\n{}".format(str(input), str(e)))
            raise e

    LOG.debug("Received input: " + json.dumps(input, indent=2))

    # Read action name from environment variable
    action_name = os.environ['ST2_ACTION']
    try:
        action_db = ACTIONS[action_name]
    except KeyError:
        raise ValueError('No action named "%s" has been installed.' % (action_name))

    # Initialize runner
    manager = DriverManager(namespace='st2common.runners.runner', invoke_on_load=False,
                            name=action_db.runner_type['name'])

    runnertype_db = RunnerTypeAPI.to_model(RunnerTypeAPI(**manager.driver.get_metadata()))

    runner = manager.driver.get_runner()

    runner._sandbox = False
    runner.runner_type_db = runnertype_db
    runner.action = action_db
    runner.action_name = action_db.name
    runner.entry_point = content_utils.get_entry_point_abs_path(pack=action_db.pack,
        entry_point=action_db.entry_point)
    runner.context = {}
    runner.libs_dir_path = content_utils.get_action_libs_abs_path(pack=action_db.pack,
        entry_point=action_db.entry_point)

    config_schema = CONFIG_SCHEMAS.get(action_db.pack, None)
    config_values = os.environ.get('ST2_CONFIG', None)
    if config_schema and config_values:
        runner._config = validate_config_against_schema(config_schema=config_schema,
                                                        config_object=json.loads(config_values),
                                                        config_path=None,
                                                        pack_name=action_db.pack)

    param_values = os.environ.get('ST2_PARAMETERS', None)
    try:
        if param_values:
            live_params = param_utils.render_live_params(
                runner_parameters=runnertype_db.runner_parameters,
                action_parameters=action_db.parameters,
                params=json.loads(param_values),
                action_context={},
                additional_contexts={
                    'input': input
                })
        else:
            live_params = input

        if debug and 'log_level' not in live_params:
            # Set log_level runner parameter
            live_params['log_level'] = 'DEBUG'

        runner_params, action_params = param_utils.render_final_params(
            runner_parameters=runnertype_db.runner_parameters,
            action_parameters=action_db.parameters,
            params=live_params,
            action_context={})
    except ParamException as e:
        raise actionrunner.ActionRunnerException(str(e))

    runner.runner_parameters = runner_params


    LOG.debug('Performing pre-run for runner: %s', runner.runner_id)
    runner.pre_run()

    (status, output, context) = runner.run(action_params)

    try:
        output['result'] = json.loads(output['result'])
    except Exception:
        pass

    output_values = os.environ.get('ST2_OUTPUT', None)
    if output_values:
        try:
            result = param_utils.render_live_params(
                runner_parameters={},
                action_parameters={},
                params=json.loads(output_values),
                action_context={},
                additional_contexts={
                    'input': input,
                    'output': output
                })
        except ParamException as e:
            raise actionrunner.ActionRunnerException(str(e))
    else:
        result = output

    output = output or {}

    if output.get('stdout', None):
        LOG.info('Action stdout: %s' % (output['stdout']))

    if output.get('stderr', None):
        LOG.info('Action stderr and logs: %s' % (output['stderr']))

    print(json.dumps(result))

if __name__ == "__main__":
    main()
