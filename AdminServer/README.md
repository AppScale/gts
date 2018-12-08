appscale-admin
==============

The appscale-admin package defines a server that allows clients to update an
AppScale deployment's configuration. The server also performs various
administrative operations to ensure that its machine is running the right
processes.

Admin API
---------
The server contains handlers that implement Google's [Admin API](
https://cloud.google.com/appengine/docs/admin-api/).

App Engine API
--------------
The server also contains handlers that allow clients to update a project's
metadata. This includes cron jobs, composite index definitions, and queue
definitions.

ServiceManager
--------------
The ServiceManager watches ZooKeeper for a list of services that it should run.
Each time that list is updated, it stops and starts processes to fulfill those
assignments.

In order to keep track of processes that it starts, the ServiceManager places
those processes in a cgroup slice. For example, all of the datastore servers
are started within the slice located at
`/sys/fs/cgroup/systemd/appscale.slice/appscale-datastore.slice`. The running
processes in that slice can be found in the `cgroup.procs` file within that
directory. When creating a slice, systemd treats a "-" within the slice name
as denoting a separator in the slice's path components.

InstanceManager
---------------
The InstanceManager performs a similar role to the ServiceManager, but it
specifically handles AppServer instances that have been assigned to its
machine.
