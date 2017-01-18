ecmcli
===========

_*CLI for Cradlepoint ECM*_

[![Maturity](https://img.shields.io/pypi/status/ecmcli.svg)](https://pypi.python.org/pypi/ecmcli)
[![License](https://img.shields.io/pypi/l/ecmcli.svg)](https://pypi.python.org/pypi/ecmcli)
[![Change Log](https://img.shields.io/badge/change-log-blue.svg)](https://github.com/mayfield/ecmcli/blob/master/CHANGELOG.md)
[![Build Status](https://semaphoreci.com/api/v1/mayfield/ecmcli/branches/master/shields_badge.svg)](https://semaphoreci.com/mayfield/ecmcli)
[![Version](https://img.shields.io/pypi/v/ecmcli.svg)](https://pypi.python.org/pypi/ecmcli)
[![Chat](https://img.shields.io/badge/gitter-chat-FF3399.svg)](https://gitter.im/mayfield/ecmcli?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

About
--------

Installation provides a command line utility (ecm) which can be used to
interact with Cradlepoint's ECM service.  Commands are subtasks of the
ECM utility.  The full list of subtasks are visible by running 'ecm --help'.


Walkthrough Video
--------
[![Walkthrough Video](http://share.gifyoutube.com/y7nLaZ.gif)](http://www.youtube.com/watch?v=fv4dWL03zPk)


Installation
--------

    python3 ./setup.py build
    python3 ./setup.py install


Compatibility
--------

* Python 3.5+


Example Usage
--------

**Viewing Device Logs**

```shell
$ ecm logs
```


**Monitoring WAN Rates**

```shell
$ ecm wanrate
 Home 2100(24400): [device is offline],          Home Router(138927): 68.1 KiB,                Home 1400(669): 0 Bytes
 Home 2100(24400): [device is offline],          Home Router(138927): 43.6 KiB,                Home 1400(669): 0 Bytes
 Home 2100(24400): [device is offline],          Home Router(138927): 40.6 KiB,                Home 1400(669): 0 Bytes
 Home 2100(24400): [device is offline],          Home Router(138927): 49.7 KiB,                Home 1400(669): 0 Bytes
```


**Rebooting a specific router**

```shell
$ ecm reboot --routers 669
Rebooting:
    Home 1400 (669)
```
