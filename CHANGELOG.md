# Change Log

## [Unreleased] - unreleased


## [9] - 2017-02-25
### Added
- Beta support for SSO login


## [8.1] - 2017-02-23
### Fixed
- Release fixes


## [8] - 2017-02-23
### Added
- Activity log


## [7.1] - 2016-11-05
### Fixed
- Update syndicate requirement for mandatory fix with new aiohttp.


## [7] - 2016-11-03
### Added
- Router `apps` command.
- `wifi` command for access point survey viewing and instigation.

### Fixed
- Honor router args to `logs -f ROUTER...`.
- Updated syndicate lib with aiohttp fixes.


## [6] - 2016-04-29
### Changed
- Moved `routers-clients` to its own command, `clients`.

### Added
- Docker support via jmayfield/ecmcli
- Log follow mode `logs -f` for doing live tail of logs.
- Feature (binding) command.


## [5] - 2015-11-15
### Changed
- Using syndicate 2 and cellulario for async basis.  No more tornado.

### Fixed
- Remotely closed HTTP connections due to server infrastructure timeouts no
  longer break calls.

### Added
- Set support for glob patterns.  This follows the bash style braces syntax.
  The `users-ls` command for example:
    users ls '{Mr,Mrs} Mayfield'
  Wildcards in the set patterns are also valid, such as `{foo*,H?m[aA]mmm}`.


## [4] - 2015-11-04
### Added
- Terms of service command: `tos`.

### Changed
- Auth failures now break a command and require you to use the `login`
  command to overcome them.  This is because shellish 2 uses pagers for
  most commands.
- Pagers everywhere.


## [3] - 2015-10-24
### Added
- Multiple output formats for remote-get command (XML, JSON, CSV, Table)
- Firmware command for status, update check and quick upgrade.
- Configuration subcommands for groups.
- accounts-delete takes N+1 arguments now.
- Messages command for user and system message viewing.
- Authorizations command.  Supports viewing and deleting authorizations.

### Changed
- Improved `debug_api` command to be more pretty; Also renamed to `trace`

### Fixed
- Command groups-edit with `--firmware` uses correct firmware product variant.
- Fix for `BlockingIOError` after using `shell` command.


## [2.4.9] - 2015-10-08
### Added
- Beta testing `remote` command to serve as replacement for `config` and `gpio`.


## [2.4.0] - 2015-10-02
### Added
- GPIO Command provided by @zvickery.

### Changed
- API connection is now encased in the ctrl-c interrupt verbosity guard.

### Fixed
- Router identity argument for reboot command.


## [2.3.0] - 2015-09-23
### Added
- 'routers clients' command will lookup MAC address hw provider.
- WiFi stats for verbose mode of 'routers clients' command.
- System wide tab completion via 'ecm completion >> ~/.bashrc'

### Changed
- Cleaner output for wanrate bps values.

### Fixed
- 'timeout' api option used flashleds command is not supported anymore.


## [2.1.0] - 2015-09-09

### Changed
- Accounts show command renamed to tree

### Added
- Accounts show command is flat table output like others


## [2.0.0] - 2015-09-04
### Added
- Major refactor to use shellish
- Much improved tab completion
- Much improved layout via shellish.Table


## [0.5.0] - 2015-07-26
### Changed
- First alpha release


[unreleased]: https://github.com/mayfield/ecmcli/compare/v9...HEAD
[9]: https://github.com/mayfield/ecmcli/compare/v8.1...v9
[8.1]: https://github.com/mayfield/ecmcli/compare/v8...v8.1
[8]: https://github.com/mayfield/ecmcli/compare/v7.1...v8
[7.1]: https://github.com/mayfield/ecmcli/compare/v7...v7.1
[7]: https://github.com/mayfield/ecmcli/compare/v6...v7
[6]: https://github.com/mayfield/ecmcli/compare/v5...v6
[5]: https://github.com/mayfield/ecmcli/compare/v4...v5
[4]: https://github.com/mayfield/ecmcli/compare/v3...v4
[3]: https://github.com/mayfield/ecmcli/compare/v2.4.9...v3
[2.4.9]: https://github.com/mayfield/ecmcli/compare/v2.4.0...v2.4.9
[2.4.0]: https://github.com/mayfield/ecmcli/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mayfield/ecmcli/compare/v2.1.0...v2.3.0
[2.1.0]: https://github.com/mayfield/ecmcli/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/mayfield/ecmcli/compare/v0.5.0...v2.0.0
[0.5.0]: https://github.com/mayfield/ecmcli/compare/eb0a415fae7344860404f92e4264c8c23f4d5cb4...v0.5.0
