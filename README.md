# SimpleSwitch 2.0
> A reimagining of Ryu's SimpleSwitch example inspired by Faucet

## Quick Start
To start the SS2 Core application, start `ryu-manager` from the root of this
package and specify the `ss2.core` module:

    $ ryu-manager ss2.core

Optionally, also start with `ryu.app.ofctl_rest` for REST API access to the
switches attached to the controller:

    $ ryu-manager ss2.core ryu.app.ofctl_rest

## Dependencies
SS2 requires the following libraries to be installed and available in the
`PYTHONPATH`:

 - Ryu 4.3+
 - Mininet 2.3+ - Required only for running unit tests

## Testing
To run the unit tests, run the following from the package root:

    $ sudo python -m unittest discover

Some tests will take a long time to run as they require setting up and tearing
down networks using Mininet. It also requires running with `sudo` as Mininet
requires `root` access for configuring the OVS kernel datapaths.
