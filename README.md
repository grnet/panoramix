# Panoramix Framework and Tools

This repository includes the Panoramix Mixnet Service and the Panoramix
Trust Control Panel.

## Panoramix Mixnet Service

This is a framework that enables setting up and running mixnets.
It employs three python packages:

  * panoramix: The main package that implements the mixnet logic
  * panoramix-service: A server implementing the panoramix API
  * panoramix-agent: A local agent for posting messages

### Installation

In each of the three packages, run:

  python setup.py install

The panoramix package includes three cryptographic backends: 'gpg', 'zeus',
and 'sphinxmix'. In order to use them, you must install the respective
dependencies with:

  pip install -r requirements_<backend>.txt

### Usage

The service can be run with `panoramix-manage runserver --nothreading`.

The panoramix package provides a wizard (panoramix-wizard) to allow the
mixnet contributors to set up a mixnet (currently works with the sphinxmix
backend only).

The panoramix-agent package provides a local agent to enable an end user to
use a mixnet. As an example, sphinxmix-agent is a wizard to configure and
launch an agent for sphinxmix. The end user can send messages to the mixnet
by posting it to the local agent, using the panoramix-client.

### Demo

Check file EXAMPLE for an extended description on how to setup and use a
sphinxmix mixnet. For a demonstration of Panoramix workflow, see
demo/README.


## Panoramix Trust Control Panel

This is a tool that provides a cryprographically secure and auditable
mechanism for configuring applications jointly by multiple mutually
untrusted authorities.

### Setup

The Trust Control Panel employs three python packages:

  * consensus-service: A server the runs negotiations among users
  * consensus-client: Client for the consensus service
  * trustpanel: The Trust Control Panel base logic

and an Ember-based web interface.

Each application that wishes to employ this tool must extend the trustpanel
base package. As an example, the repository includes an extension for the
Zeus E-voting System (directory zeus_trust).

### Deployment

The tool can be deployed using docker. From the root directory, run:

  ./docker/create-dev.sh

By default, the Zeus extension is installed and run. The Trust Control Panel
is accessible at <http://localhost:9000/ui/trustee1/>.

Extensions for other applications must be registered in the file
`docker/services.conf`.


## Panoramix Horizon 2020

This project has received funding from the European Union’s Horizon 2020
Research and Innovation Programme under Grant Agreement No 653497.

## Copyright and license

Copyright (C) 2016-2019 GRNET S.A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
