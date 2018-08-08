import tensorflow as tf 
from tensorflow.contrib.seq2seq.python.ops.decoder import Decoder


__all__ = ["dynamic_bidecode", "dynamic_bidecode_att"]



def dynamic_bidecode(fw_decoder, bw_decoder,
                   output_time_major=False,
                   impute_finished=False,
                   maximum_iterations=None,
                   parallel_iterations=32,
                   swap_memory=False,
                   scope=None,return_seq=False):
  """Perform dynamic decoding with `bidecoder`."""
  if not isinstance(fw_decoder, Decoder):
    raise TypeError("Expected fw_decoder to be type Decoder, but saw: %s" %
                 type(fw_decoder))

  if not isinstance(bw_decoder, Decoder):
    raise TypeError("Expected bw_decoder to be type Decoder, but saw: %s" %
                 type(bw_decoder))

  with tf.variable_scope(scope,"bi_decoder") as scope:
    # Forward
    with tf.variable_scope("fw") as fw_scope:
      fw_final_outputs, fw_final_state, fw_final_sequence_lengths = tf.contrib.seq2seq.dynamic_decode(
        fw_decoder, output_time_major=output_time_major, 
        impute_finished=impute_finished, 
        maximum_iterations=maximum_iterations,
        parallel_iterations=parallel_iterations, 
        swap_memory=swap_memory,
        scope=fw_scope
      )

    # Backward direction
    if not output_time_major:
      time_dim = 1
      batch_dim = 0
    else:
      time_dim = 0
      batch_dim = 1

    def _reverse(input_, seq_lengths, seq_dim, batch_dim):
      if seq_lengths is not None:
        return tf.reverse_sequence(
            input=input_, seq_lengths=seq_lengths,
            seq_dim=seq_dim, batch_dim=batch_dim)
      else:
        return tf.reverse(input_, axis=[seq_dim])

    with tf.variable_scope("bw") as bw_scope:
      bw_final_outputs, bw_final_state, bw_final_sequence_lengths = tf.contrib.seq2seq.dynamic_decode(
        bw_decoder, output_time_major=output_time_major, 
        impute_finished=impute_finished, 
        maximum_iterations=maximum_iterations,
        parallel_iterations=parallel_iterations, 
        swap_memory=swap_memory,
        scope=bw_scope
      )
  
  if not isinstance(fw_decoder, tf.contrib.seq2seq.BeamSearchDecoder):
    # no beam search
    fw_rnn_output = fw_final_outputs.rnn_output
    bw_rnn_output = bw_final_outputs.rnn_output
  else:
    fw_rnn_output = tf.no_op()
    bw_rnn_output = tf.no_op()

  rnn_outputs = (fw_rnn_output, bw_rnn_output)
  output_states = (fw_final_state, bw_final_state)
  decoder_outputs = (fw_final_outputs, bw_final_outputs)
  final_seq_lengths = (fw_final_sequence_lengths, bw_final_sequence_lengths)

  if return_seq == False:
    return (rnn_outputs, output_states, decoder_outputs)
  else:
    return (rnn_outputs, output_states, decoder_outputs, final_seq_lengths)


def dynamic_bidecode_att(fw_decoder, bw_decoder,
                   output_time_major=False,
                   impute_finished=False,
                   maximum_iterations=None,
                   parallel_iterations=32,
                   swap_memory=False,
                   scope=None):
  first_bidecode = dynamic_bidecode(fw_decoder, bw_decoder,
                                    output_time_major,
                                    impute_finished,
                                    maximum_iterations,
                                    parallel_iterations,
                                    swap_memory,
                                    scope, True)
  # first, run fw and bw decode with default attention
  with tf.control_dependencies([first_bidecode]):
    #second, assign rnn_output to new attention.values
    (rnn_outputs, _, _, final_seq_lengths) =  first_bidecode
    fw_rnn_output, bw_rnn_output = rnn_outputs
    fw_rnn_lengths, bw_rnn_lengths = final_seq_lengths

    fw_assgin = fw_decoder.set_attention_values(fw_rnn_output, fw_rnn_lengths)
    bw_assgin = bw_decoder.set_attention_values(bw_rnn_output, bw_rnn_lengths)

    with tf.control_dependencies([fw_assgin, bw_assgin]):
      # third, re-run dynamic_bidecode and return
      return dynamic_bidecode(fw_decoder, bw_decoder,
                                    output_time_major,
                                    impute_finished,
                                    maximum_iterations,
                                    parallel_iterations,
                                    swap_memory,
                                    scope)