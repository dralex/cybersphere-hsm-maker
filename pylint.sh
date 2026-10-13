#!/bin/bash

# W0621: the pytest fixtures are redefined by design
# E0712, E0705: pylint does not see the exception classes of the binding
pylint --disable=I1101,C0301,W0703,W0621,R0801,E0712,E0705 hsm_maker tests
