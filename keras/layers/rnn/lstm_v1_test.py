# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================
"""Tests for LSTM V1 layer."""

import copy

from absl.testing import parameterized
import keras
from keras.testing_infra import test_combinations
from keras.testing_infra import test_utils
import numpy as np
import tensorflow.compat.v2 as tf


@test_combinations.run_all_keras_modes
class LSTMLayerTest(test_combinations.TestCase):

  def test_return_sequences_LSTM(self):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    test_utils.layer_test(
        keras.layers.LSTM,
        kwargs={'units': units,
                'return_sequences': True},
        input_shape=(num_samples, timesteps, embedding_dim))

  @tf.test.disable_with_predicate(
      pred=tf.test.is_built_with_rocm,
      skip_message='Double type is yet not supported in ROCm')
  @test_utils.run_v2_only
  def test_float64_LSTM(self):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    test_utils.layer_test(
        keras.layers.LSTM,
        kwargs={'units': units,
                'return_sequences': True,
                'dtype': 'float64'},
        input_shape=(num_samples, timesteps, embedding_dim),
        input_dtype='float64')

  def test_static_shape_inference_LSTM(self):
    # Github issue: 15165
    timesteps = 3
    embedding_dim = 4
    units = 2

    model = keras.models.Sequential()
    inputs = keras.layers.Dense(embedding_dim,
                                input_shape=(timesteps, embedding_dim))
    model.add(inputs)
    layer = keras.layers.LSTM(units, return_sequences=True)
    model.add(layer)
    outputs = model.layers[-1].output
    self.assertEqual(outputs.shape.as_list(), [None, timesteps, units])

  def test_dynamic_behavior_LSTM(self):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    layer = keras.layers.LSTM(units, input_shape=(None, embedding_dim))
    model = keras.models.Sequential()
    model.add(layer)
    model.compile(
        'rmsprop',
        'mse',
        run_eagerly=test_utils.should_run_eagerly())

    x = np.random.random((num_samples, timesteps, embedding_dim))
    y = np.random.random((num_samples, units))
    model.train_on_batch(x, y)

  def test_dropout_LSTM(self):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    test_utils.layer_test(
        keras.layers.LSTM,
        kwargs={'units': units,
                'dropout': 0.1,
                'recurrent_dropout': 0.1},
        input_shape=(num_samples, timesteps, embedding_dim))

  def test_recurrent_dropout_with_implementation_restriction(self):
    layer = keras.layers.LSTM(2, recurrent_dropout=0.1, implementation=2)
    # The implementation is force to 1 due to the limit of recurrent_dropout.
    self.assertEqual(layer.implementation, 1)

  @parameterized.parameters([0, 1, 2])
  def test_implementation_mode_LSTM(self, implementation_mode):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    test_utils.layer_test(
        keras.layers.LSTM,
        kwargs={'units': units,
                'implementation': implementation_mode},
        input_shape=(num_samples, timesteps, embedding_dim))

  def test_constraints_LSTM(self):
    embedding_dim = 4
    layer_class = keras.layers.LSTM
    k_constraint = keras.constraints.max_norm(0.01)
    r_constraint = keras.constraints.max_norm(0.01)
    b_constraint = keras.constraints.max_norm(0.01)
    layer = layer_class(
        5,
        return_sequences=False,
        weights=None,
        input_shape=(None, embedding_dim),
        kernel_constraint=k_constraint,
        recurrent_constraint=r_constraint,
        bias_constraint=b_constraint)
    layer.build((None, None, embedding_dim))
    self.assertEqual(layer.cell.kernel.constraint, k_constraint)
    self.assertEqual(layer.cell.recurrent_kernel.constraint, r_constraint)
    self.assertEqual(layer.cell.bias.constraint, b_constraint)

  @parameterized.parameters([True, False])
  @tf.test.disable_with_predicate(
      pred=tf.test.is_built_with_rocm,
      skip_message='Skipping as ROCm MIOpen does not support padded input.')
  def test_with_masking_layer_LSTM(self, unroll):
    layer_class = keras.layers.LSTM
    inputs = np.random.random((2, 3, 4))
    targets = np.abs(np.random.random((2, 3, 5)))
    targets /= targets.sum(axis=-1, keepdims=True)
    model = keras.models.Sequential()
    model.add(keras.layers.Masking(input_shape=(3, 4)))
    model.add(layer_class(units=5, return_sequences=True, unroll=unroll))
    model.compile(
        loss='categorical_crossentropy',
        optimizer='rmsprop',
        run_eagerly=test_utils.should_run_eagerly())
    model.fit(inputs, targets, epochs=1, batch_size=2, verbose=1)

  @parameterized.parameters([True, False])
  def test_masking_with_stacking_LSTM(self, unroll):
    inputs = np.random.random((2, 3, 4))
    targets = np.abs(np.random.random((2, 3, 5)))
    targets /= targets.sum(axis=-1, keepdims=True)
    model = keras.models.Sequential()
    model.add(keras.layers.Masking(input_shape=(3, 4)))
    lstm_cells = [keras.layers.LSTMCell(10), keras.layers.LSTMCell(5)]
    model.add(keras.layers.RNN(
        lstm_cells, return_sequences=True, unroll=unroll))
    model.compile(
        loss='categorical_crossentropy',
        optimizer='rmsprop',
        run_eagerly=test_utils.should_run_eagerly())
    model.fit(inputs, targets, epochs=1, batch_size=2, verbose=1)

  def test_from_config_LSTM(self):
    layer_class = keras.layers.LSTM
    for stateful in (False, True):
      l1 = layer_class(units=1, stateful=stateful)
      l2 = layer_class.from_config(l1.get_config())
      assert l1.get_config() == l2.get_config()

  def test_deep_copy_LSTM(self):
    cell = keras.layers.LSTMCell(5)
    copied_cell = copy.deepcopy(cell)
    self.assertEqual(copied_cell.units, 5)
    self.assertEqual(cell.get_config(), copied_cell.get_config())

  def test_specify_initial_state_keras_tensor(self):
    num_states = 2
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    # Test with Keras tensor
    inputs = keras.Input((timesteps, embedding_dim))
    initial_state = [keras.Input((units,)) for _ in range(num_states)]
    layer = keras.layers.LSTM(units)
    if len(initial_state) == 1:
      output = layer(inputs, initial_state=initial_state[0])
    else:
      output = layer(inputs, initial_state=initial_state)
    self.assertTrue(
        any(initial_state[0] is t
            for t in layer._inbound_nodes[0].input_tensors))

    model = keras.models.Model([inputs] + initial_state, output)
    model.compile(
        loss='categorical_crossentropy',
        optimizer=tf.compat.v1.train.AdamOptimizer(),
        run_eagerly=test_utils.should_run_eagerly())

    inputs = np.random.random((num_samples, timesteps, embedding_dim))
    initial_state = [np.random.random((num_samples, units))
                     for _ in range(num_states)]
    targets = np.random.random((num_samples, units))
    model.train_on_batch([inputs] + initial_state, targets)

  def test_specify_initial_state_non_keras_tensor(self):
    num_states = 2
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    # Test with non-Keras tensor
    inputs = keras.Input((timesteps, embedding_dim))
    initial_state = [keras.backend.random_normal_variable(
        (num_samples, units), 0, 1)
                     for _ in range(num_states)]
    layer = keras.layers.LSTM(units)
    output = layer(inputs, initial_state=initial_state)

    model = keras.models.Model(inputs, output)
    model.compile(
        loss='categorical_crossentropy',
        optimizer=tf.compat.v1.train.AdamOptimizer(),
        run_eagerly=test_utils.should_run_eagerly())

    inputs = np.random.random((num_samples, timesteps, embedding_dim))
    targets = np.random.random((num_samples, units))
    model.train_on_batch(inputs, targets)

  def test_reset_states_with_values(self):
    num_states = 2
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    layer = keras.layers.LSTM(units, stateful=True)
    layer.build((num_samples, timesteps, embedding_dim))
    layer.reset_states()
    assert len(layer.states) == num_states
    assert layer.states[0] is not None
    self.assertAllClose(
        keras.backend.eval(layer.states[0]),
        np.zeros(keras.backend.int_shape(layer.states[0])),
        atol=1e-4)
    state_shapes = [keras.backend.int_shape(state) for state in layer.states]
    values = [np.ones(shape) for shape in state_shapes]
    if len(values) == 1:
      values = values[0]
    layer.reset_states(values)
    self.assertAllClose(
        keras.backend.eval(layer.states[0]),
        np.ones(keras.backend.int_shape(layer.states[0])),
        atol=1e-4)

    # Test with invalid data
    with self.assertRaises(ValueError):
      layer.reset_states([1] * (len(layer.states) + 1))

  def test_specify_state_with_masking(self):
    num_states = 2
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    inputs = keras.Input((timesteps, embedding_dim))
    _ = keras.layers.Masking()(inputs)
    initial_state = [keras.Input((units,)) for _ in range(num_states)]
    output = keras.layers.LSTM(units)(inputs, initial_state=initial_state)

    model = keras.models.Model([inputs] + initial_state, output)
    model.compile(
        loss='categorical_crossentropy',
        optimizer='rmsprop',
        run_eagerly=test_utils.should_run_eagerly())

    inputs = np.random.random((num_samples, timesteps, embedding_dim))
    initial_state = [np.random.random((num_samples, units))
                     for _ in range(num_states)]
    targets = np.random.random((num_samples, units))
    model.train_on_batch([inputs] + initial_state, targets)

  def test_return_state(self):
    num_states = 2
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    inputs = keras.Input(batch_shape=(num_samples, timesteps, embedding_dim))
    layer = keras.layers.LSTM(units, return_state=True, stateful=True)
    outputs = layer(inputs)
    state = outputs[1:]
    assert len(state) == num_states
    model = keras.models.Model(inputs, state[0])

    inputs = np.random.random((num_samples, timesteps, embedding_dim))
    state = model.predict(inputs)
    self.assertAllClose(keras.backend.eval(layer.states[0]), state, atol=1e-4)

  def test_state_reuse(self):
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2

    inputs = keras.Input(batch_shape=(num_samples, timesteps, embedding_dim))
    layer = keras.layers.LSTM(units, return_state=True, return_sequences=True)
    outputs = layer(inputs)
    output, state = outputs[0], outputs[1:]
    output = keras.layers.LSTM(units)(output, initial_state=state)
    model = keras.models.Model(inputs, output)

    inputs = np.random.random((num_samples, timesteps, embedding_dim))
    outputs = model.predict(inputs)

  def test_initial_states_as_other_inputs(self):
    timesteps = 3
    embedding_dim = 4
    units = 3
    num_samples = 2
    num_states = 2
    layer_class = keras.layers.LSTM

    # Test with Keras tensor
    main_inputs = keras.Input((timesteps, embedding_dim))
    initial_state = [keras.Input((units,)) for _ in range(num_states)]
    inputs = [main_inputs] + initial_state

    layer = layer_class(units)
    output = layer(inputs)
    self.assertTrue(
        any(initial_state[0] is t
            for t in layer._inbound_nodes[0].input_tensors))

    model = keras.models.Model(inputs, output)
    model.compile(
        loss='categorical_crossentropy',
        optimizer=tf.compat.v1.train.AdamOptimizer(),
        run_eagerly=test_utils.should_run_eagerly())

    main_inputs = np.random.random((num_samples, timesteps, embedding_dim))
    initial_state = [np.random.random((num_samples, units))
                     for _ in range(num_states)]
    targets = np.random.random((num_samples, units))
    model.train_on_batch([main_inputs] + initial_state, targets)

  def test_regularizers_LSTM(self):
    embedding_dim = 4
    layer_class = keras.layers.LSTM
    layer = layer_class(
        5,
        return_sequences=False,
        weights=None,
        input_shape=(None, embedding_dim),
        kernel_regularizer=keras.regularizers.l1(0.01),
        recurrent_regularizer=keras.regularizers.l1(0.01),
        bias_regularizer='l2',
        activity_regularizer='l1')
    layer.build((None, None, 2))
    self.assertEqual(len(layer.losses), 3)
    x = keras.backend.variable(np.ones((2, 3, 2)))
    layer(x)
    if tf.executing_eagerly():
      self.assertEqual(len(layer.losses), 4)
    else:
      self.assertEqual(len(layer.get_losses_for(x)), 1)

  @tf.test.disable_with_predicate(
      pred=tf.test.is_built_with_rocm,
      skip_message='Skipping as ROCm MIOpen does not support padded input.')
  def test_statefulness_LSTM(self):
    num_samples = 2
    timesteps = 3
    embedding_dim = 4
    units = 2
    layer_class = keras.layers.LSTM
    model = keras.models.Sequential()
    model.add(
        keras.layers.Embedding(
            4,
            embedding_dim,
            mask_zero=True,
            input_length=timesteps,
            batch_input_shape=(num_samples, timesteps)))
    layer = layer_class(
        units, return_sequences=False, stateful=True, weights=None)
    model.add(layer)
    model.compile(
        optimizer=tf.compat.v1.train.GradientDescentOptimizer(0.01),
        loss='mse',
        run_eagerly=test_utils.should_run_eagerly())
    out1 = model.predict(np.ones((num_samples, timesteps)))
    self.assertEqual(out1.shape, (num_samples, units))

    # train once so that the states change
    model.train_on_batch(
        np.ones((num_samples, timesteps)), np.ones((num_samples, units)))
    out2 = model.predict(np.ones((num_samples, timesteps)))

    # if the state is not reset, output should be different
    self.assertNotEqual(out1.max(), out2.max())

    # check that output changes after states are reset
    # (even though the model itself didn't change)
    layer.reset_states()
    out3 = model.predict(np.ones((num_samples, timesteps)))
    self.assertNotEqual(out2.max(), out3.max())

    # check that container-level reset_states() works
    model.reset_states()
    out4 = model.predict(np.ones((num_samples, timesteps)))
    self.assertAllClose(out3, out4, atol=1e-5)

    # check that the call to `predict` updated the states
    out5 = model.predict(np.ones((num_samples, timesteps)))
    self.assertNotEqual(out4.max(), out5.max())

    # Check masking
    layer.reset_states()

    left_padded_input = np.ones((num_samples, timesteps))
    left_padded_input[0, :1] = 0
    left_padded_input[1, :2] = 0
    out6 = model.predict(left_padded_input)

    layer.reset_states()

    right_padded_input = np.ones((num_samples, timesteps))
    right_padded_input[0, -1:] = 0
    right_padded_input[1, -2:] = 0
    out7 = model.predict(right_padded_input)

    self.assertAllClose(out7, out6, atol=1e-5)


if __name__ == '__main__':
  tf.test.main()
