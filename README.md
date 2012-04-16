<pre>
 _____         _____ _ _ 
|     |___ ___|     | |_|
| | | | . |   |   --| | |
|_|_|_|___|_|_|_____|_|_|
             experimental           
</pre>

The experimental branch of Moncli is a complete rewrite of the original 0.x series.
It will be the base of all further Moncli development.

Some features have been remove and quite a lot has been added.

Features:

* Gevent based, fast and lightweight.
* Modular approach using Wishbone.
* AMQP8 support with reconnection strategy.
* Process request to execute plugins.
* Processes incoming events over UDP.
* AMQP queue/exchange destination can be dynamically defined per request or event.
* Has build in scheduler able to repeat requests.
* I/O JSON schema validation.

This release of MonCli is not complete yet.
