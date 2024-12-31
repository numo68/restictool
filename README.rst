Usage
=====

**restictool** is a Python wrapper to the dockerized `restic <https://restic.net>`_ backup tool.

The tool allows to backup docker volumes and local directories, to restore
a snapshot to a local directory, to run arbitrary restic commands and
just to check the configuration file.

 ::

    restictool -h|--help
    restictool COMMAND [-h|--help]
    restictool [TOOL_ARGS...] COMMAND [COMMAND_ARGS...] [--] [...]

The rest of the arguments is passed to the restic command. In case the
such argument is a one recognized by the command as well,
use ``--`` as a separator. Any unrecognized argument starting with
the dash is also passed to the restic command, check this if you are
getting weird errors.

As seen from the ``restic`` the snapshots created with the backup commands are
``/volume/VOLNAME`` for docker volumes and ``/localdir/TAG`` for locally
specified ones. This needs to be considered when specifying inclusion
or exclusion filters for both backup and restore. If for example
``/a/b`` is being backed up as ``my_dir``, the original
file ``a/b/c/d`` is seen as ``/localdir/my_dir/c/d``.


The container running ``restic`` gets a ``restictool.local`` added to the hosts
pointing to the gateway of the first IPAM configuration in the default bridge
network. You can use this for tunneled setups.


Common arguments
----------------

``-h``, ``--help``
   show the help message and exit. If COMMAND is present, shows the help
   for the command

``-c FILE``, ``--config FILE``
   the configuration file (default: ``~/.config/restic/restictool.yml``)

``--cache DIR``
   the cache directory (default: ``~/.cache/restic``)

``--image IMAGE``
   the docker restic image name (default: ``restic/restic``)

``--force-pull``
   force pulling of the docker image first

``--log-level``
   log level for the tool (``critical``, ``error``, ``warning``,
   ``info``, ``debug``, default: ``warning``). This applies to the tool itself;
   messages from the restic are written to the standard output directly
   and can be silenced by ``-q`` passed to either for this tool or
   the restic command

``-q``, ``--quiet``
   Pass the ``-q`` option to the restic command

``COMMAND``
   one of ``backup``, ``restore``, ``snapshots``, ``run``,
   ``dockerdr``, ``exists`` or ``check``

Restore arguments
-----------------

``-r DIR``, ``--restore DIR``
   directory to restore to. This argument is mandatory.
``SNAPSHOT``
   snapshot to restore from

The snapshot to restore from is taken from the next argument; if not present
it defaults to ``latest``. A common way to restore is ``--path /localdir/my_name``
finding the latest snapshot containing the specified local directory.

The directory will be created if it does not exist. Note that as
the restored files are written from inside the docker container they will
be written from the context of the root user. Watch for mishaps.

Docker disaster recovery arguments
----------------------------------

The docker disaster recovery restores all the volumes existing both on the
local system and the backup to the latest snapshot. The list of the
volumes in the configuration is ignored, as are volume-specific options.

The data are restored to a directory derived from the mountpoint of the volume,
meaning that if the volume resides on ``/var/lib/docker/volumes/foo/_data``
it will be restored to ``/var/lib/docker/volumes/foo/_data.restored``.

Snapshots arguments
-------------------

Any argument is passed to the ``restic snapshots`` directly.
``--latest 1`` is a common one.

Run arguments
-------------

Any argument is passed to the ``restic`` directly.

Configuration file
==================

The ``restictool`` needs a configuration file
(default ``~/.config/restic/restictool.yml``) to specify the restic
repository configuration. As the file contains secrets such as
the repository password, take care to set reasonable permissions.
The file is in the `YAML <https://yaml.org/>`_ format.

Repository configuration
------------------------

.. code-block:: yaml

    repository:
        location: "s3:https://somewhere:8010/restic-backups"
        password: "MySecretPassword"
        host: myhost
        network_from: myvpncontainer
        authentication:
            AWS_ACCESS_KEY_ID: "S3:SomeKeyId"
            AWS_SECRET_ACCESS_KEY: "someSecret"
        extra:
            RESTIC_PACK_SIZE: "64"

``location`` and ``password`` are mandatory. All other fields are optional.

``password`` specifies the ``restic`` repository password. Fetching
the repository location or password from a file or command is not
supported.

``host`` defaults to the hostname of the machine the ``restictool`` is
executed on. It only applies to ``backup``.

The optional ``network_from`` specifies the name of the container to reuse
the network stack from. This allows using VPN tunnels or other non-standard
networking. The container has to be already started.

``authentication`` contains ``restic`` environment variables used to
authenticate against the target repository. Typical ones are
``AWS_ACCESS_KEY_ID`` or ``AWS_SECRET_ACCESS_KEY``. ``extra`` contains
other variables such as ``RESTIC_COMPRESSION``. This is only an
logical division and both sets of variables will be merged.

The variable names will be converted to uppercase and the values passed 1:1.
Some variables cannot be defined (for example ``RESTIC_CACHE_DIR`` or
``RESTIC_PASSWORD``).

Logging configuration
---------------------

If the default of logging to the standard error is not suitable, the logging
configuration can be provided via the ``logging`` key. The content has to conform
to the `Python logging facility dictionary schema <https://docs.python.org/3/library/logging.config.html#logging-config-dictschema>`_.
If provided, the ``--log-level`` command-line option is used to set the level
for the logger named ``console``, if there is any.

The following extra arguments can be used in the formatters: ``operation``, ``repoLocation``,
``repoHost``, ``object``, ``elapsed`` meaning the performed operation, repository location and name,
the object being backed up and the time the operation took. All are strings except
the elapsed time that is in seconds as float.

**CAUTION**: The ``DEBUG`` level logs sensitive information such as secret keys and passwords.

.. code-block:: yaml

    logging:
        version: 1
        root:
            handlers:
                - console
                - file
                - syslog
            level: INFO
        handlers:
            console:
                class: logging.StreamHandler
                level: INFO
                formatter: detailed
                stream: ext://sys.stderr
            file:
                class: logging.handlers.RotatingFileHandler
                level: INFO
                formatter: detailed
                filename: /tmp/restictool.log
                maxBytes: 65536
                backupCount: 3
            syslog:
                class: logging.handlers.SysLogHandler
                level: INFO
                address: !!python/tuple ["my.syslog.lan",514]
                facility: daemon
                formatter: syslog
        formatters:
            detailed:
                format: '%(asctime)s %(levelname)s op=%(operation)s repo=%(repoLocation)s host=%(repoHost)s object=%(object)s time=%(elapsed).1fs msg=%(message)s'
                datefmt: '%Y-%m-%d %H:%M:%S'
            syslog:
                format: 'restictool[%(process)d] %(levelname)s op=%(operation)s repo=%(repoLocation)s host=%(repoHost)s object=%(object)s time=%(elapsed).1fs msg=%(message)s'

Observability
-------------

The backups done can be exported through prometheus text-file format and consumed
by the node exporter's textfile collector. If the ``metrics`` key exists, the file
is atomically populated after each backup run by the data of the latest snapshots.

.. code-block:: yaml

    metrics:
        directory: "/var/local/lib/prom_metrics"
        suffix: "s3"

``directory`` is mandatory and specifies the path of the directory passed as the
``--collector.textfile.directory`` for the ``node_exporter``. It has to already exist.
``suffix`` is optional and will be appended to the file name to distinguish metrics
files generated by different ``restictool`` configurations. For the above configuration
the full file name will be ``/var/local/lib/prom_metrics/restictool-s3.prom``.

Command-line options for restic
-------------------------------

.. code-block:: yaml

    options:
        common:
            - "--insecure-tls"
        forget:
            - ...
        prune:
            - ...
        volume:
            - ...
        localdir:
            - ...

This section specifies the command-line options to be used when
executing the ``restic``. ``common`` ones are used for any run,
``volume`` ones are added to common ones when backing up a docker
volume and ``localdir`` ones when backing up a local directory.
The ``run`` and ``restore`` commands get just the ``common`` ones.

If ``forget`` is present a ``restic forget`` is run after the
backup is completed with these arguments. If ``'DEFAULT'``
is specified for forget it is expanded to
``--keep-daily 7 --keep-weekly 5 --keep-monthly 12``.

If ``prune`` is specified, a ``restic prune`` is run following
the ``forget``, with the specified arguments (if any). Note that
this can be costly on a cloud storage charging for API calls
and downloads.


Volume backup specification
---------------------------

.. code-block:: yaml

    volumes:
      - name: my_volume
        options:
          - '--exclude="/volume/my_volume/some_dir"'
          - "--exclude-caches"

``volumes`` is a list of the docker volumes to backup when running
the  ``backup`` command. ``options`` will be used when backing up
the specified volume. 

.. code-block:: yaml

    volumes:
      - name: '*'
        exclude:
          - without_this_volume
        options:
          - '--exclude="/volume/my_volume/some_dir"'
          - "--exclude-caches"

If the name is ``'*'``, all non-anonymous (not 48+ hex characters) volumes
that are not mentioned in the ``exclude`` list are backed up. If there is
both ``*`` and a specific name, the options will come from the specific one
and if not found, from the wildcard one. If the name is not ``'*'``, ``exclude``
is ignored.

Local directory backup specification
------------------------------------

.. code-block:: yaml

    localdirs:
      - name: my_tag
        path: path
        options:
          - '--exclude="/localdir/my_tag/some_dir"'

``localdirs`` is a list of the local directories to backup when running
the  ``backup`` command. ``name`` specifies the tag that will be used
to distinguish the directories in the repository.  ``options``
will be used when backing up the specified local directory. Tildes (``~``)
at the beginning of ``path`` will be expanded to the contents
of the ``HOME`` environment variable.

