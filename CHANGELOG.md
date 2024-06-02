# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

## [1.5](https://pypi.org/project/futured/1.5/) - 2024-06-02
### Changed
* Python >=3.9 required

### Added
* `gevent` greenlet support

## [1.4](https://pypi.org/project/futured/1.4/) - 2023-05-06
### Changed
* Python >=3.8 required

## [1.3](https://pypi.org/project/futured/1.3/) - 2021-09-12
### Changed
* Python >=3.7 required
* Python 3.10 event loop changes
* Streams replaced with tasks

## [1.2](https://pypi.org/project/futured/1.2/) - 2020-11-24
* Python >=3.6 required

## [1.1](https://pypi.org/project/futured/1.1/) - 2019-12-14
* Stream completed futures from a pending pool

## [1.0](https://pypi.org/project/futured/1.0/) - 2019-07-21
* Executed functions are context managers
* `starmap` supported

## [0.3](https://pypi.org/project/futured/0.3/) - 2018-08-18
* `forked` has optional maximum number of workers
* `waiting` context manager
* `command` pipes (`|`)
* `distributed.Client` support

## [0.2](https://pypi.org/project/futured/0.2/) - 2017-09-17
* `command.coroutine` creates asyncio subprocesses
* `futured.mapzip` generates results zipped with arguments
* `asynced.run` supports asynchronous iterators
