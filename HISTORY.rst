=======
History
=======

0.7.0 (2026-01-19)
------------------
* Dropped official support for Python < 3.10, added official support for Python
  3.10 and later.
* Fixed bug with ``ftl2elm --watch`` mode triggering on too many file system events.
* Cleanups.

0.6.0 (2020-04-09)
------------------
* Big rewrite of the type inference/checking mechanism, with more accurate
  error messages now.

0.5.0 (2019-08-15)
------------------
* Updated to Syntax 1.0 (fluent.syntax 0.15)
* Various bug fixes and small improvements

0.4.0 (2019-03-18)
------------------
* ftl2elm --include option
* Dropped Python 2.7 support

0.3.0 (2019-03-06)
------------------

* Syntax 0.8 support, including parameterized terms.
* Better compile-time resolution of some expressions.

0.2.1 (2018-12-19)
------------------

* Fixed python-fluent dependency to an older version (< 0.9), because it
  doesn't work with newer versions. Thanks @stasm for the report.

0.2.0 (2018-09-10)
------------------

* Better handling for a large variety of error conditions
* Proper fallback mechanism implemented
* Added ``--watch`` option.
* Eliminate unused imports from generated code
* Various bug fixes:

  * Avoid outputting ``.elm`` files with no exports
  * Bugs with HTML attributes and non-string message args
  * Crasher with multi-line messages
  * Crasher when a message is missing from default locale


0.1.0 (2018-07-27)
------------------

* First release on PyPI.
