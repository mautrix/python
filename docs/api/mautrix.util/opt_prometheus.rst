opt\_prometheus
===============

The opt\_prometheus module contains no-op implementations of prometheus's
``Counter``, ``Gauge``, ``Summary``, ``Histogram``, ``Info`` and ``Enum``,
as well as a helper method for timing async methods. It's useful for creating
metrics unconditionally without a hard dependency on prometheus\_client.

.. attribute:: is_installed

   A boolean indicating whether ``prometheus_client`` was successfully imported.

   :type: bool
   :canonical: mautrix.util.opt_prometheus.is_installed

.. decorator:: async_time(metric)

   Measure the time that each execution of the decorated async function takes.

   This is equivalent to the ``time`` method-decorator in the metrics, but
   supports async functions.

   :param Gauge/Summary/Histogram metric: The metric instance to store the measures in.
   :canonical: mautrix.util.opt_prometheus.async_time
