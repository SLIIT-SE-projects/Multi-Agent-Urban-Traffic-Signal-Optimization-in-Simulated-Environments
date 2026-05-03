# Emergency Vehicle Preemption Service.
#
# Receives enriched snapshots from the Simulation Manager every step,
# runs ETA prediction (TF/Keras) + safety classification (sklearn) +
# multi-EV priority arbitration, returns override directives that the
# Manager applies via TraCI.
