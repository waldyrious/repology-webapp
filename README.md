# Repology

[![Build Status](https://travis-ci.org/AMDmi3/repology.svg?branch=master)](https://travis-ci.org/AMDmi3/repology)
[![Coverage Status](https://coveralls.io/repos/github/AMDmi3/repology/badge.svg?branch=master)](https://coveralls.io/github/AMDmi3/repology?branch=master)

![Example report](docs/screenshot.png)

Repology tracks and compares package versions along multiple
repositories including Arch, Chocolatey, Debian, Fedora, FreeBSD,
Gentoo, Mageia, OpenBSD, OpenSUSE, pkgsrc, Sisyphus, SlackBuilds,
Ubuntu and more.

## Uses

- **Users**:
  - Compare completeness and freshness of package repositories,
    choose most up to date distro
  - Find out what repositories contain newest versions of packages
    you need
- **Package/port maintainers**:
  - Another way to track new releases of software you package
  - Compete with other distros in keeping up to date
  - Find fellow maintainers to resolve packaging problems together
  - Keep package naming and versioning schemes in sync to other
    repos for your and your user's convenience
- **Software authors**:
  - Keep track of how well your project is packaged
  - Keep in touch with your product package maintainers
  - If you're not using [semantic versioning](http://semver.org/)
    yet, see how useful it is

# Status

Repology is currently in an early phase of development, with a goal
of creating usable utility in a quick and dirty way. For now, it is
usable in two modes: as a command line generator of single HTML
report and a static website generator for [repology.org](repology.org).

## Howto

### Dependencies

Mandatory:

- [Python](https://www.python.org/) 3.x
- Python module [pyyaml](http://pyyaml.org/)
- Python module [requests](http://python-requests.org/)
- Python module [rubymarshal](https://github.com/d9pouces/RubyMarshal)

Optional, needed for parsing some repositories:

- [wget](https://www.gnu.org/software/wget/)
- [git](https://git-scm.com/)
- [librpm](http://www.rpm.org/) and [pkg-config](https://www.freedesktop.org/wiki/Software/pkg-config/)

Optional, for web-application:

- Python module [flask](http://flask.pocoo.org/)
- Python module [psycopg](http://initd.org/psycopg/)
- [https://www.postgresql.org/](PostgreSQL database) 9.5+

Optional, for doing HTML validation when running tests:
- Python module [pytidylib](https://pypi.python.org/pypi/pytidylib) and [tidy-html5](http://www.html-tidy.org/) library

### Building

Though repology is mostly a Python project, it contains C utility to
read binary rpm format, which is used for parsing ALT Sisyphus
repository. To build the utility, run ```make``` in project root.
You need librpm and pkg-config.

### Usage

#### Configuration

First, you may need to tune settings which are shared by all repology
utilities, such as directory for storing downloaded repository state
or DSN (string which specifies how to connect to PostgreSQL database).
See ```repology.conf.default``` for default values, create
```repology.conf``` in the same directory to override them or
specify path to alternative config in ```REPOLOGY_SETTINGS```
environment variable, or override settings via command line.

By default, repology uses ```./_state``` state directory and
```repology/repology/repology``` database/user/password on localhost.

#### Fetching/updating repository data

First, let's try to fetch some repository data and see if it works.
No database is needed at this point.

```
./repology-update --fetch --parse
```

* ```--fetch``` tells the utility to fetch raw repository data
(download files, scrape websites, clone git repos) into state
directory. Note that it won't refetch (update) data unless
```--update``` is also specified.
* ```--parse``` parses downloaded raw data into internal format
which is also saved into state directory.

After data is downloaded you may inspect it with

```
./repology-dump.py | less
```

The utility allows filtering and several modes of operation, see
```--help``` for full list of options.

#### Creating the database

To run repology webapp you need PostgreSQL database.

First, ensure PostgreSQL server is installed and running,
and execute the following SQL queries (usually you'll run
```psql -U postgres``` for this):

```
CREATE DATABASE repology;
CREATE USER repology WITH PASSWORD 'repology';
GRANT ALL ON DATABASE repology TO repology;
```

now you can create database schema (tables, indexes etc.) with:

```
./repology-update --initdb
```

and finally push parsed data into the database with:

```
./repology-update --database
```

#### Running the webapp

Repology is a flask application, so as long as you've set up
database and configuration, you may just run the application
locally:

```
./repology-app.py
```

and point your browser to http://127.0.0.1:5000/ to view the
site. This should be enough for personal usage, experiments and
testing.

Alternatively, you may deploy the application in numerous ways,
including mod_wsgi, uwsgi, fastcgi and plain CGI application. See
[flask documentation on deployment](http://flask.pocoo.org/docs/0.11/deploying/)
for more info.

#### Keeping up to date

To keep repository data up to date, you'll need to periodically
refetch it and update the database. Note there's no need to recreate
database schema every time (unless it needs changing). Everything
can be done with single command:

```
./repology-app.py --fetch --update --parse --database
```

## Repository support

As much data as possible is parsed from each repo. Package name and
version are always parsed.

| Repository                       | Summary | Maint-r | Categ | WWW | License | Download |
|----------------------------------|:-------:|:-------:|:-----:|:---:|:-------:|:--------:|
| ALT Sisyphus                     | ✔       | ✔       | ✔     |     |         |          |
| Arch                             | ✔       | ✔       |       | ✔   | ✔       |          |
| CentOS, Fedora, Mageia, OpenSUSE | ✔       |         | ✔     | ✔   | ✔       |          |
| Chocolatey                       | ✔       |         |       | ✔   |         |          |
| CPAN                             |         | ✔       |       | ✔   |         |          |
| Debian, Ubuntu                   |         | ✔       | ✔     | ✔   |         |          |
| F-Droid                          |         |         | ✔     | ✔   | ✔       |          |
| FreeBSD                          | ✔       | ✔       | ✔     | ✔   |         |          |
| freshcode.club                   | ✔       | n/a     |       | ✔   |         |          |
| Gentoo                           | ✔       | ✔       | ✔     | ✔   | ✔ (1)   | ✔ (1)    |
| Guix                             | ✔       |         |       | ✔   | ✔       |          |
| GoboLinux                        | ✔       |         |       | ✔   | ✔       |          |
| OpenBSD                          | ✔       | ✔       | ✔     |     |         |          |
| pkgsrc                           | ✔       | ✔       | ✔     |     |         |          |
| PyPi                             | ✔       |         |       | ✔   |         |          |
| SlackBuilds                      |         | ✔       | ✔     | ✔   |         | ✔        |
| YACP                             |         |         |       |     |         |          |

(1) Gentoo support is not complete, complex cases like condional downloads and licenses
are ignored for now.

## Reading the report

Report is HTML table, columns correspond to repositories and rows
correspond to packages. Cells hold package versions, highlighted
as follows:

- ```cyan```: package is only present in a single repo: nothing to
              compare version to, and may be local artifact
- ```green```: package up to date
- ```red```: package outdated (there's newer version in some other repo)
- ```yellow```: there are multiple packages some of which are up to date
                and others are outdated
- ```gray```: version was manually ignored, likely because of broken
              versioning scheme

Note that there may be multiple packages of a same name in a single repo
(either naturally, or because of name transformations).

## Documentation

- [Rules guide](docs/RULES.md)

## Author

* [Dmitry Marakasov](https://github.com/AMDmi3) <amdmi3@amdmi3.ru>

## License

GPLv3 or later, see [COPYING](COPYING).
