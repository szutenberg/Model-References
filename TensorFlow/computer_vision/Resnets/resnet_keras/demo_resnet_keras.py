#!/usr/bin/env python3

###############################################################################
# Copyright (C) 2020-2021 Habana Labs, Ltd. an Intel Company
###############################################################################

import argparse
import os
import subprocess

from TensorFlow.common.common import setup_jemalloc, setup_preloading
from central.training_run_config import TrainingRunHWConfig

def set_lars_hyperparams(unknown_args):
    if '--base_learning_rate' not in unknown_args:
        unknown_args.extend(['--base_learning_rate', '9.5'])
    if '--warmup_epochs' not in unknown_args:
        unknown_args.extend(['--warmup_epochs', '3'])
    if '--lr_schedule' not in unknown_args:
        unknown_args.extend(['--lr_schedule', 'polynomial'])
    if '--label_smoothing' not in unknown_args:
        unknown_args.extend(['--label_smoothing', '0.1'])
    if '--weight_decay' not in unknown_args:
        unknown_args.extend(['--weight_decay', '0.0001'])
    if '--single_l2_loss_op' not in unknown_args:
        unknown_args.append('--single_l2_loss_op')

def main():
    parser = argparse.ArgumentParser(add_help=False, usage=argparse.SUPPRESS)
    parser.add_argument("--num_workers_per_hls", default=1, type=int)
    parser.add_argument("--hls_type", default="HLS1", type=str)
    parser.add_argument("--kubernetes_run", default=False, type=bool)
    args, unknown_args = parser.parse_known_args()
    script_to_run = str(os.path.abspath(os.path.join(os.path.dirname(__file__), "resnet_ctl_imagenet_main.py")))

    if '--help' in unknown_args or '-h' in unknown_args:
        print(
        """\ndemo_resnet_keras.py is a distributed launcher for resnet_ctl_imagenet_main.py.
        \nusage: python demo_resnet_keras.py [arguments]
        \noptional arguments:\n

        -dt <data_type>,   --dtype <data_type>                  Data type, possible values: fp32, bf16. Defaults to fp32
        -dlit <data_type>, --data_loader_image_type <data_type> Data loader images output. Should normally be set to the same data_type as the '--dtype' param
        -bs <batch_size>,  --batch_size <batch_size>            Batch size, defaults to 256
        -te <epochs>,      --train_epochs <epochs>              Number of training epochs, defaults to 1
        -dd <data_dir>,    --data_dir <data_dir>                Data dir, defaults to `/data/tensorflow_datasets/imagenet/tf_records/`.
                                                                Needs to be specified if the above does not exists.
        -md <model_dir>,   --model_dir <model_dir>              Model dir, defaults to /tmp/resnet
                           --clean                              If set, model_dir will be removed if it exists. Unset by default
                           --train_steps <steps>                Max train steps
                           --log_steps <steps>                  How often display step status, defaults to 100
                           --steps_per_loop <steps>             Number of steps per training loop. Will be capped at steps per epoch, defaults to 50.
                           --enable_checkpoint_and_export       Enables checkpoint callbacks and exports the saved model.
                           --enable_tensorboard                 Enables Tensorboard callbacks.
        -ebe <epochs>      --epochs_between_evals <epochs>      Number of training epochs between evaluations, defaults to 1.
                           --experimental_preloading            Enables support for 'data.experimental.prefetch_to_device' TensorFlow operator.
                                                                If set, loads dynpatch_prf_remote_call.so (via LD_PRELOAD)
                           --optimizer <optimizer_type>         Name of optimizer preset, possible values: SGD, LARS. Defaults to SGD.
                           --num_workers_per_hls <num_workers>  Number of workers per node. Defaults to 1.
                                                                In case num_workers_per_hls > 1, it runs 'resnet_ctl_imagenet_main.py [ARGS]' via mpirun with generated HCL config.
                                                                Must be used together with --use_horovod either --distribution_strategy
                           --use_horovod                        Enable horovod for multicard scenarios
                           --distribution_strategy <strategy>   The Distribution Strategy to use for training. Defaults to off
                           --hls_type <hls_type>                HLS type: either HLS1 (8-cards) or HLS1-H (4-cards). Defaults to HLS1.
                           --kubernetes_run                     Setup kubernetes run for multi HLS training
        \nexamples:\n
        python3 demo_resnet_keras.py
        python3 demo_resnet_keras.py -dt bf16 -dlit bf16 --experimental_preloading -bs 256
        python3 demo_resnet_keras.py -te 90 --optimizer LARS -bs 128
        python3 demo_resnet_keras.py --dtype bf16 -dlit bf16 --use_horovod --num_workers_per_hls 8 -te 40 --optimizer LARS -bs 256
        \nIn order to see all possible arguments to resnet_ctl_imagenet_main.py, run "python resnet_ctl_imagenet_main.py --helpfull"
        """)
        exit(0)

    # libjemalloc for better allocations
    setup_jemalloc()

    if '--experimental_preloading' in unknown_args:
        setup_preloading()

    if '--horovod_hierarchical_allreduce' in unknown_args:
        os.environ['HOROVOD_HIERARCHICAL_ALLREDUCE'] = "1"

    if '--optimizer LARS' in ' '.join(map(str, unknown_args)):
        set_lars_hyperparams(unknown_args)

    if args.num_workers_per_hls > 1:
        if '--use_horovod' in unknown_args:
            hw_config = TrainingRunHWConfig(scaleout=True, num_workers_per_hls=args.num_workers_per_hls,
                                            hls_type=args.hls_type, kubernetes_run=args.kubernetes_run,
                                            output_filename="demo_resnet_keras_log")
            cmd = list(hw_config.mpirun_cmd.split(" ")) + ["python3", script_to_run]
        elif any("--distribution_strategy" in s for s in unknown_args):
            hw_config = TrainingRunHWConfig(scaleout=True, num_workers_per_hls=args.num_workers_per_hls,
                                            hls_type=args.hls_type, kubernetes_run=args.kubernetes_run,
                                            output_filename="demo_resnet_keras_log")
            cmd = list(hw_config.mpirun_cmd.split(" ")) + ["python3", script_to_run, '--use_tf_while_loop=False']
        else:
            raise RuntimeError('You need to pass either --use_horovod or --distribution_strategy hpu if num_workers_per_hls>1')
    else:
        cmd = ["python3", script_to_run]

    cmd.extend(unknown_args)
    cmd_str = ' '.join(map(str, cmd))
    print(f"Running: {cmd_str}", flush=True)
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()