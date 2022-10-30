Usage
=====

**restictool** is a Pyhton wrapper to the dockerized `restic <https://restic.net>`_ backup tool.

The tool allows to backup docker volumes and local directories, to restore
a snapshot to a local directory, to run arbitrary restic commands and
just to check the configuration file.

 ::

    restictool -h|--help
    restictool COMMAND [-h|--help]
    restictool [TOOL_ARGS...] COMMAND [COMMAND_ARGS...] [--] [...]

The rest of the arguments is passed to the restic command. In case the
such argument is a one recognized by the command as well,
use ``--`` as a separator.

As seen from the ``restic`` the snapshots created with the backup commands are
``/volume/VOLNAME`` for docker volumes and ``/localdir/TAG`` for locally
specified ones. This needs to be considered when specifying inclusion
or exclusion filters for both backup and restore.

The container running ``restic`` gets a ``restictool.local`` added to the hosts
pointing to the gateway of the first config in the default bridge network. You
can use this for tunneled setups.


Common arguments
----------------

``-h``, ``--help``
   show the help message and exit. If COMMAND is present, shows the help
   for the command

``-c FILE``, ``--c FILE``
   the configuration file (default: ``~/.config/restic/restictool.yml``)

``--cache DIR``
   the cache directory (default: ``~/.cache/.restic``)

``--image IMAGE``
   the docker restic image name (default: ``restic/restic``)

``--force-pull``
   force pulling of the docker image first

``-q``
   be quiet

``-v``
   be verbose. Repeat for increasing verbosity level

``COMMAND``
   one of ``backup``, ``restore``, ``run`` or ``check``

Backup arguments
----------------

``-p``
   prune after backup. This can be costly on cloud storage
   charging for API calls and downloads

Restore arguments
-----------------

``-r DIR``, ``--restore DIR``
   directory to restore to. This argument is mandatory.

The command requires at least the definition of the snapshot to restore
from. Usually filters will be specified as well.

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
executed on.

``authentication`` contains ``restic`` environment variables used to
authenticate against the target repository. Typical ones are
``AWS_ACCESS_KEY_ID`` or ``AWS_SECRET_ACCESS_KEY``. ``extra`` contains
other variables such as ``RESTIC_COMPRESSION``. This is only an
logical division and both sets of variables will be merged.

The variable names will be converted to uppercase and the values passed 1:1.
Some variables cannot be defined (for example ``RESTIC_CACHE_DIR`` or
``RESTIC_PASSWORD``).

Command-line options for restic
-------------------------------

.. code-block:: yaml

    options:
        common:
            - "--insecure-tls"
        volume:
            - ...
        localdir:
            - ...

This section specifies the command-line options to be used when
executing the ``restic``. ``common`` ones are used for any run,
``volume`` ones are added to common ones when backing up a docker
volume and ``localdir`` ones when backing up a local directory.
The ``run`` and ``restore`` commands get just the ``common`` ones.

Volume backup specification
---------------------------

.. code-block:: yaml

    volumes:
      - name: my_volume
        options:
          - '--exclude="/volume/my_volume/some_dir"'
          - "--exclude-caches"

``volumes`` is a list of the docker volumes to backup when running
the  ``backup`` command. If the name is ``*``, all non-anonymous
(not 48+ hex characters) volumes are backed up. ``options``
will be used when backing up the specified volume. If there is
both ``*`` and a specific name, the options will come from the
specific one and if not found, from the wildcard one.


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
will be used when backing up the specified local directory.
