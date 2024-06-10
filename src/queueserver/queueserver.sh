#!/bin/bash

# Set up configuration
THIS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export HAVEN_CONFIG_FILES="${BLUESKY_DIR}/iconfig.toml"
KAFKA_TOPIC=`haven_config queueserver.kafka_topic`
ZMQ_CONTROL_ADDR="tcp://*:`haven_config queueserver.control_port`"
ZMQ_INFO_ADDR="tcp://*:`haven_config queueserver.info_port`"

# Lauch 
start-re-manager \
    --startup-script ${THIS_DIR}/queueserver_startup.py \
    --existing-plans-devices ${BLUESKY_DIR}/queueserver_existing_plans_and_devices.yaml \
    --user-group-permissions ${THIS_DIR}/queueserver_user_group_permissions.yaml \
    --zmq-control-addr ${ZMQ_CONTROL_ADDR} \
    --zmq-info-addr ${ZMQ_INFO_ADDR} \
    --redis-addr ${REDIS_ADDR} \
    --keep-re \
    --kafka-topic ${KAFKA_TOPIC} \
    --update-existing-plans-devices ENVIRONMENT_OPEN
