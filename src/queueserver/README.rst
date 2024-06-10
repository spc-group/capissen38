Queueserver Configuration
=========================

Configuration and setup for running a bluesky-queueserver and related
tools (kafka, redis, mongo_consumer)

Full setup of the spectroscopy group's queueserver stack involves the
following parts

- **redis:** In-memory database holding queueserver history.
- **queueserver:** Runs the bluesky plans.
- **kafka:** Scalable database holds documents produced by queueserver.
- **zookeeper:** Manager for controlling the kafka server.
- **mongo_consumer:** Reads the documents from kafka and stores them in mongoDB.

The command ``haven_config`` is used in several places to retrieve
configuration from a single .toml file. For non-Haven deployment,
replace `haven_config <key>` with the appropriate values.

Systemd Units
-------------

Starting and stopping these services is done through systemd
units. The mongo_consumer is the top-level unit, and so **starting
mongo_consumer.service is enough to start the remaining services**.

1. Copy the contents of ``systemd-units`` into ``~/.config/systemd/user/``
2. Modify the units as described in the sections below.
3. Reload the modified unit files: ``systemctl --user daemon-reload``
4. Start mongo_consumer: ``systemctl --user start mongo_consumer``
5. [Optional] View console output of all services: ``journalctl -xef --user``
6. [Optional] View console output of a specific unit (e.g. kafka): ``journalctl -xef --user --unit=kafka.service``
7. [Optional] Enable mongo_consumer to start on boot: ``systemctl --user enable mongo_consumer``

A useful pattern is to set environmental variables in each systemd
unit file, and read these environmental variables in the various
python and shell scripts. This allows, for example, multiple
queueserver instances to be run with different ZMQ ports.

The systemd unit files **assume** the various bluesky tools are
installed in a micromamba environment named *haven*, and that this
repository is cloned to ``~/src/queueserver``. **Modify the systemd
unit files to use the correct environment and repository location.**

The systemd unit files are also capable of **setting PVs based on the
service's state**. For example, by uncommenting the lines
``ExecStopPost=...`` and ``ExecStartPost=`` in each systemd unit file,
EPICS PVs can be toggled when the units start and stop, possibly
alerting staff or users that the queueserver pipeline is not
functioning.

Multiple QueueServers
---------------------

It is possible to have multiple queueservers running, for example if
multiple branches are operating at a single beamline. In this case,
independent instances of queueserver will be started and will need
unique zeroMQ ports. These ports will be set in ``queueserver.sh`` and
so that file should be modified as needed to read ZMQ ports from
config files or environmental variables. Multiple copies of the
systemd unit (``queueserver.service``) should be made with the
correspoding environmental variables.

Each queueserver will have a unique kafka topic. One kafka server will
run with multiple topics, and one (or more, at scale) mongo_consumer
instances will run with a dictionary of topic <=> mongodb-catalog
mappings.

Redis
-----

Redis should be installed by AES-IT on the target system. The
system-wide systemd unit will not be used since it requires root
access to start and stop. No modification of the systemd unit-file is
necessary.

Queueserver
-----------

1. Install haven in a micromamba environment.
2. Modify ``.config/systemd/user/queueserver.service`` to use the
   correct conda environment, and point to the location of this repo
   and the correct bluesky directory (if needed).

Kafka/Zookeeper
---------------

Kafka tutorial taken from https://linuxconfig.org/how-to-install-kafka-on-redhat-8

We will run a pre-built binary of Kafka and zookeeper. System-wide
installation from RHEL package repos might be preferred to take
advantage of automatic upgrades.

In this tutorial, the kafka installation will be in ``/local/s25staff/``.

1. ``cd /local/s25staff``
2. Download the latest binary from https://kafka.apache.org/downloads
3. Confirm download integrity (e.g. ``sha512sum kafka_2.13-3.3.1.tgz``) and compare to SHA512 sum on downloads website.
4. Unzip kafka: ``tar -zxvf kafka_2.13-3.3.1.tgz``
5. Create a symbolic link (makes upgrades easier): ``ln -s kafka_2.13-3.3.1 kafka``
6. Modify ``~/.config/systemd/user/zookeeper.service`` to point to the
   correct kafka directory, and also the config file in this
   repository.
7. Modify ``~/.config/systemd/user/kafka.service`` to point to the
   correct kafka directory, and also the config file in this
   repository.   
8. Reload systemd units: ``systemctl --user daemon-reload``
9. Start kafka and zookeeper: ``systemctl --user start kafka``

To confirm it is running, check the output of ``systemctl --user
status kafka`` and
``journalctl -xef --user --unit=kafka.service``. Possibly also check
the output of ``lsof -i :9092`` to ensure kafka is listening on the
correct port.

Once the kafka server is running, we will **create a topic** that will
be used by both the queueserver and any consumers
(e.g. mongo_consumer). In this tutorial, we will use
"s25idc_queueserver"; **modify as needed**. More than one topic is
allowed; you should have one topic for each instance of
queueserver. These options are suitable for small scale at a single
beamline; more partitions and/or replication may be necessary at
scale.

10. ``cd /local/s25staff/kafka``
11. Create the kafka topic ``./bin/kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic s25idc_queueserver``
   
[Optional] Confirm that messages can be successfully passed around the
Kafka server. We will not use these tools for production, but might be
helpful for troubleshooting.

12. ``cd /local/s25staff/kafka``
13. Launch a consumer to watch the topic: ``./kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic s25idc_queueserver``
14. In a second terminal, launch a producer to post messages: ``./kafka-console-producer.sh --broker-list localhost:9092 --topic s25idc_queueserver``
15. Type a message into the producer prompt and verify it appears in the producer.


Mongo Consumer
--------------

Mongo consumer polls the kafka topic and saves the documents to the
mongodb database.

1. Modify ``mongo_consumer.py`` in this repository:
   
   1. Set the correct database URI *mongo_uri*.
   2. Modify *topics* to be a list of topics to listen on.
   3. Set *topic_database_map* to map kafka topics to mongo database catalogs.
   
2. Modify ``.config/systemd/user/mongo_consumer.service`` to use the
   correct conda environment and point to this source repo.
3. Start mongo_consumer: ``systemctl --user start mongo_consumer``
4. [Optional] Enable mongo_consumer start on boot: ``systemctl --user enable mongo_consumer``

Bluesky Kafka Python Client
---------------------------

To receive queueserver documents from the kafka server in python, use
the bluesky-kafka python library. For example, to print the text to
the console from a client computer:

.. code:: python

   from bluesky_kafka import BlueskyConsumer
   consumer = BlueskyConsumer(["s25idc_queueserver"], bootstrap_servers="myserver.xray.aps.anl.gov:9092", group_id="print.document.group", process_document=lambda consumer, topic, name, doc: print([name, doc]))
   consumer.start()
