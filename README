 _____         _____ _ _ 
|     |___ ___|     | |_|
| | | | . |   |   --| | |
|_|_|_|___|_|_|_____|_|_|
                         
Moncli is a generic MONitoring CLIent which executes and processes requests on an external system in order to interact with 
the host's local information sources which are normally not available over the network.
Once Moncli has executed and evaluated the request it submits the check results back into the message broker infrastructure, 
where the results are ready to be by another process.

* Powerful and flexible communication:
	All communication going from and to MonCli goes over the RabbitMQ message broker.  This allows us to leverage all qualities
	RabbitMQ has to offer into your monitoring setup.

* Easy but powerful configuration:
	Moncli receives all assignments and commands through the message broker infrastructure.  All events MonCli should perform
	are defined in JSON format.  This allows you to control all Moncli instances efficiently from a centralized location with just
	submitting a JSON document.

* Have more checks on your monitoring server:
	Moncli has a built in scheduler. This scheduler receives a one time configuration of what to execute and evaluate. The 
	scheduler repeats that check at the cycle you defined in this configuration. From that moment on, the results just flow 
	into your monitoring system as passive checks without any effort required from your Monitoring server's scheduler. That 
	significantly offloads the load on your monitoring server. Changing the properties of such a scheduled check is as 
	simple as just submitting a new configuration to Moncli. The status of the scheduler along with the configurations is 
	also written to disk on regular intervals so Moncli just continues working after a restart.

* Simplify plugin/check development:
	Moncli uses as a data source plugins which only have to produce key/value pairs. Creating a script which only produces 
	that kind of information is pretty easy and makes development of plugins accessible to non programmers.

* Improve plugin quality:
	Moncli has all evaluation logic and other goodies built in so you don't have to worry about that when creating plugins.
	This standardizes the results more and improves the level of plugin quality.

* Deliver more helpful information:
	Moncli plugins can optionally produce verbose information at your choice which rolls up into your Nagios interface. 
	This is helpful for engineers who are debugging a certain problem.

* Built-in plugin update system:
	Moncli has a built-in update system which allows you to transparently update the plugins from a centralized repository.

* Resilience:
	When your monitoring infrastructure is not available or reachable all check results are queued in the broker environment,
	waiting to be processed.  When a server is not online, all submitted commands will wait in the queue until MonCli picks
	them up.

* Security:
	Only plugins with the correct hash can be executed which prevents the execution of changed or non conform plugins.

* Compatibility:
	Moncli works together with monitoring frameworks which are based upon or derived from Nagios Core. It allows you 
	to work with Nagios as you are used to it.

* Ease of distribution:
	Moncli is written in Python. Once you have all its dependencies installed, you can "freeze" Moncli into a stand 
	alone executable, which facilitates distribution to your nodes.


For installation instruction please visit:

	http://www.smetj.net/wiki/Moncli_documentation
