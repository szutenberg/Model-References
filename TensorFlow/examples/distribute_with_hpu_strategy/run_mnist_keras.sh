#!/bin/bash
# Copyright (C) 2021 Habana Labs, Ltd. an Intel Company
echo "Distributed MNIST Training using Keras"
echo "An example of multi-worker training using HPUStrategy"

SCRIPT_PATH="`dirname \"$0\"`"          # A relative path from the current working directory to the directory containing this script.
MODEL_GARDEN="$SCRIPT_PATH/../../.."    # A relative path from the current working directory to 'model_garden' directory.
NUM_WORKERS=${NUM_WORKERS:-2}           # Number of worker processes participating in a training cluster.

echo NUM_WORKERS=$NUM_WORKERS

# Spawn several processes running the same Python training script.
# This example takes advantage of 'mpirun' of OpenMPI package.
# Note: OpenMPI is not mandatory for distributed training with HPUStrategy.
set -x
PYTHONPATH="$PYTHONPATH:$SCRIPT_PATH" \
    mpirun -np $NUM_WORKERS --tag-output --allow-run-as-root $PYTHON -m mnist_keras "$@"
set +x
