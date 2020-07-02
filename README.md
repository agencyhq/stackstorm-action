StackStorm Actions
==================

Run almost the entire collection of StackStorm actions as docker containers.

## Usage

Build container with the packs of you want to use with

```
docker build --build-arg packs="stackstorm-time" -t st2actions/stackstorm-time .
```

then run them with

```
docker run -i -e ST2_ACTION=stackstorm-time.parse_date_string -e ST2_PARAMETERS='{"date_string": "1 week ago"}' st2actions/stackstorm-time
```

You can build a container with multiple packs by using

```
docker build --build-arg packs="stackstorm-urbandict stackstorm-time" -t st2actions/my-collection .
```

You can also build base container, run it indefinitely and then bootstrap it with packs and run actions with `docker exec`

```
export CONTAINER=$(docker run -d st2actions/base tail -f /dev/null)

docker exec -i $CONTAINER ./bootstrap.sh stackstorm-time

docker exec -i \
  -e ST2_ACTION=stackstorm-time.parse_date_string \
  -e ST2_PARAMETERS='{"date_string": "1 week ago"}' \
  $CONTAINER ./entrypoint.sh python handler.py
```

Also, most of the times you would likely want to pipe the results of the execution to some other tool (read `jq`). You can filter output of `docker run` by using `-a stdout` as every logging message should end up in stderr and stdout should only contain a json of the execution results

```
docker run -i -e ST2_ACTION=stackstorm-time.parse_date_string -e ST2_PARAMETERS='{"date_string": "1 week ago"}' -a stdout st2actions/stackstorm-time
```

## Limitations

Currently, the tool only supports python runner. Though, last time I checked, overwhelming majority of actions in StackStorm Exchange were using python runner.
