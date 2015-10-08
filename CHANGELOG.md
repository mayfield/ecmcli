# Change Log

## [Unreleased] - unreleased


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
- Much imporoved layout via shellish.Table


## [0.5.0] - 2015-07-26
### Changed
- First alpha release


[unreleased]: https://github.com/mayfield/ecmcli/compare/v2.4.9...HEAD
[2.4.9]: https://github.com/mayfield/ecmcli/compare/v2.4.0...v2.4.9
[2.4.0]: https://github.com/mayfield/ecmcli/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mayfield/ecmcli/compare/v2.1.0...v2.3.0
[2.1.0]: https://github.com/mayfield/ecmcli/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/mayfield/ecmcli/compare/v0.5.0...v2.0.0
[0.5.0]: https://github.com/mayfield/ecmcli/compare/eb0a415fae7344860404f92e4264c8c23f4d5cb4...v0.5.0
