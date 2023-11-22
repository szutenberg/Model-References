# coding=utf-8
# Copyright (c) 2023 Habana Labs, Ltd. an Intel Company.
# Copyright (c) 2020, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This code is copied fron NVIDIA apex:
      https://github.com/NVIDIA/apex
   with some changes. """

import numbers
import torch
from torch.nn.parameter import Parameter
from torch.nn import init
import importlib
from megatron import get_args
from torch.nn.functional import layer_norm
from megatron.global_vars import get_current_device

global fused_mix_prec_layer_norm_cuda
fused_mix_prec_layer_norm_cuda = None


class FusedLayerNormAffineFunction(torch.autograd.Function):

  @staticmethod
  def forward(ctx, input, weight, bias, normalized_shape, eps):

    ctx.normalized_shape = normalized_shape
    ctx.eps = eps
    input_ = input.contiguous()
    weight_ = weight.contiguous()
    bias_ = bias.contiguous()
    output, mean, invvar = fused_mix_prec_layer_norm_cuda.forward_affine(
        input_, ctx.normalized_shape, weight_, bias_, ctx.eps)
    ctx.save_for_backward(input_, weight_, bias_, mean, invvar)

    return output


  @staticmethod
  def backward(ctx, grad_output):

    input_, weight_, bias_, mean, invvar = ctx.saved_tensors
    grad_input = grad_weight = grad_bias = None
    grad_input, grad_weight, grad_bias \
      = fused_mix_prec_layer_norm_cuda.backward_affine(
        grad_output.contiguous(), mean, invvar,
        input_, ctx.normalized_shape,
        weight_, bias_, ctx.eps)

    return grad_input, grad_weight, grad_bias, None, None



class MixedFusedLayerNorm(torch.nn.Module):

  def __init__(self, normalized_shape, eps=1e-5, sequence_parallel=False):
        super(MixedFusedLayerNorm, self).__init__()
        args = get_args()
        if args.use_hpu:
          self.layer_norm_func = self._native_layer_norm_helper
        else:
          global fused_mix_prec_layer_norm_cuda
          fused_mix_prec_layer_norm_cuda = importlib.import_module(
            "fused_mix_prec_layer_norm_cuda")
          self.layer_norm_func = FusedLayerNormAffineFunction.apply

        if isinstance(normalized_shape, numbers.Integral):
            normalized_shape = (normalized_shape,)
        self.normalized_shape = torch.Size(normalized_shape)
        self.eps = eps

        self.weight = Parameter(torch.empty(
                    *normalized_shape,
                    device=get_current_device(),
                    dtype=args.params_dtype))

        self.bias = Parameter(torch.empty(
                    *normalized_shape,
                    device=get_current_device(),
                    dtype=args.params_dtype))

        self.reset_parameters()

        if sequence_parallel:
            # set sequence parallelism flag on weight and bias parameters
            setattr(self.weight, 'sequence_parallel', True)
            setattr(self.bias, 'sequence_parallel', True)

  def _native_layer_norm_helper(self, input, weight, bias, normalized_shape, eps):
    return layer_norm(input, normalized_shape, weight, bias, eps)


  def reset_parameters(self):
    # Init the layernorm weight to 0 if apply_layernorm_weight_plus_one is set, we will add the 1 in the forward function
    # when calling the layernorm function
    args = get_args()
    if args.apply_layernorm_weight_plus_one:
        init.zeros_(self.weight)
    else:
        init.ones_(self.weight)

    init.zeros_(self.bias)


  def forward(self, input):

    args = get_args()
    if args.apply_layernorm_weight_plus_one:
        return self.layer_norm_func(input, self.weight + 1, self.bias, self.normalized_shape, self.eps)
    else:
        return self.layer_norm_func(input, self.weight, self.bias, self.normalized_shape, self.eps)
