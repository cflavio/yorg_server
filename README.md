Yorg server
===========

**Yorg** is an *open source* racing game developed by Ya2 using [Panda3D](http://www.panda3d.org) for *Windows*, *OSX* and *Linux*. More information can be found on [this page](http://www.ya2.it/pages/yorg.html).

This repository contains the Yorg's **server component**.

It requires *Python 3.x*. It should be cloned recursively since [yyagl submodule](https://github.com/cflavio/yyagl) and [yracing submodule](https://github.com/cflavio/yracing) are used.

Here's a short guide about installing and preparing your environment for Yorg server. The following instructions are *for Linux*, the commands for other operative systems are analogous.

* clone the repository: `git clone --recursive https://github.com/cflavio/yorg_server.git`
* go into the directory: `cd yorg_server`
* (optional, recommended for non-developers, since *master* is an unstable branch) checkout the *stable* branch: `git checkout stable; git submodule foreach git checkout stable`
* create a python3 virtualenv: `virtualenv --python=/usr/bin/python3 venv`
* activate the virtualenv: `. ./venv/bin/activate`
* install the prerequisites: `pip install panda3d`
* edit the file `settings.json` and insert your information
* launch the game server: `python main.py &`
* launch the web server: `python webserver.py &`
    * the web server runs on the port 9090, so you must manage this in your web server: e.g. (*lighttpd*): `$HTTP["host"] == "your.host.tld" { proxy.server = ( "" => ( ("host" => "127.0.0.1", "port" => 9090) ) ) }`
* make sure that the port you've chosen is open: e.g. `sudo ufw status`.

Yorg's client
-------------

In order to use your server in place of the default one, edit the file `options.yaml` (which is created after the first execution of Yorg to store your settings).

The path of `options.yaml` is:

* Windows: *C:\\Users\\username\\AppData\\Local\\Yorg\\*
* OSX: *~/Documents/Yorg/*
* Linux: *~/.local/share/Yorg/*

You have to update the `development:server` setting from the default one (`ya2tech.it:9099`) to yours.
