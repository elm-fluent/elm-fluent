=======
History
=======

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
