import collections

import sys
from mpl_toolkits.axes_grid1 import host_subplot
from mpl_toolkits import axisartist
from matplotlib import pyplot
import numpy
import csv
import os


class TimeSeries(object):
  def __init__(self, logs_dir):
    self.start_timestamp = None
    self.logs_dir = logs_dir
    self.scale_log_file = os.path.join(self.logs_dir, "scale.csv")
    self.proxy_stats_log_file = None
    self.node_stats_log_files = []
    self.find_log_files()

    scale_stats = self.prepare_scale_stats()
    self.scale_time = numpy.array([row[0] for row in scale_stats])
    self.nodes = numpy.array([row[1] for row in scale_stats])
    self.appservers = numpy.array([row[2] for row in scale_stats])
    self.pending = numpy.array([row[3] for row in scale_stats])
    self.min_capacity = numpy.array([row[2]*7*0.9 for row in scale_stats])
    self.max_capacity = numpy.array([row[2]*7*0.7 for row in scale_stats])

    proxy_stats = self.prepare_proxy_stats()
    self.reqs_time = numpy.array([row[0] for row in proxy_stats])
    self.req_rate = numpy.array([row[1] for row in proxy_stats])
    self.qcur = numpy.array([row[2] for row in proxy_stats])
    self.scur = numpy.array([row[3] for row in proxy_stats])
    self.err_rate = numpy.array([row[4] for row in proxy_stats])

    nodes_stats = self.prepare_nodes_stats()
    self.utilization_time = numpy.array([row[0] for row in nodes_stats])
    self.min_cpu_utilization = numpy.array([row[1] for row in nodes_stats])
    self.avg_cpu_utilization = numpy.array([row[2] for row in nodes_stats])
    self.max_cpu_utilization = numpy.array([row[3] for row in nodes_stats])
    self.min_memory_utilization = numpy.array([row[4] for row in nodes_stats])
    self.avg_memory_utilization = numpy.array([row[5] for row in nodes_stats])
    self.max_memory_utilization = numpy.array([row[6] for row in nodes_stats])
    self.min_loadavg = numpy.array([row[7] for row in nodes_stats])
    self.avg_loadavg = numpy.array([row[8] for row in nodes_stats])
    self.max_loadavg = numpy.array([row[9] for row in nodes_stats])

  def prepare_scale_stats(self):
    with open(self.scale_log_file) as stats_file:
      csv_reader = csv.reader(stats_file)
      next(csv_reader)
      first_row = next(csv_reader)
      self.start_timestamp = float(first_row[0])
      return [
        (float(row[0]) - self.start_timestamp, int(row[1]), int(row[2]), int(row[3]))
        for row in csv_reader
      ]

  def prepare_proxy_stats(self):
    with open(self.proxy_stats_log_file) as stats_file:
      csv_reader = csv.reader(stats_file)
      next(csv_reader)
      stats = []
      prev_errors = 0
      prev_timestamp = -2
      for row in csv_reader:
        req_rate = int(row[7])
        qcur = int(row[9])
        scur = int(row[10])
        hrsp_5xx = int(row[11])
        if hrsp_5xx < prev_errors:
          errors = hrsp_5xx
          prev_errors= errors
        else:
          errors = hrsp_5xx - prev_errors
          prev_errors= hrsp_5xx
        # timestamp, req_total, 5xx
        test_time = int(float(row[0])) - self.start_timestamp + 60*60*7
        errors_rate = errors // (test_time - prev_timestamp)
        prev_timestamp = test_time
        stats.append((test_time, req_rate, qcur, scur, errors_rate))
      return stats

  def prepare_nodes_stats(self):
    common_timeline = collections.defaultdict(list)
    for node_file in self.node_stats_log_files:
      with open(node_file) as node_stats_file:
        csv_reader = csv.reader(node_stats_file)
        next(csv_reader)
        for row in csv_reader:
          test_time = int(float(row[0])) - self.start_timestamp + 60*60*7
          rounded_time = (test_time // 45) * 45
          common_timeline[rounded_time].append(
            (float(row[1]), float(row[2]), float(row[3]), float(row[4]))
          )

    nodes_stats = []
    for test_time in sorted(common_timeline):
      moment_stats = common_timeline[test_time]
      cpu_percent = [row[0] / row[1] for row in moment_stats]
      memory_percent = [
        100.0 - (100.0 * row[2] / 7844724736) for row in moment_stats
      ]
      loadavg = [row[3] / row[1] for row in moment_stats]
      nodes_count = len(moment_stats)
      nodes_stats.append((
        test_time,
        min(cpu_percent),
        sum(cpu_percent) / nodes_count,
        max(cpu_percent),
        min(memory_percent),
        sum(memory_percent) / nodes_count,
        max(memory_percent),
        min(loadavg),
        sum(loadavg) / nodes_count,
        max(loadavg),
      ))

    return nodes_stats

  def find_log_files(self):
    for sub_dir, dirs, files in os.walk(self.logs_dir):
      for f in files:
        if f == "node.csv":
          self.node_stats_log_files.append(os.path.join(sub_dir, f))
        elif f == "gae_validity-test.csv":
          self.proxy_stats_log_file = os.path.join(sub_dir, f)


def main(logs_dir, start_time, end_time):
  time_series = TimeSeries(logs_dir)

  # Proxy data arrays:
  reqs_time = time_series.reqs_time
  reqs_per_sec = savitzky_golay(time_series.req_rate, 7, 4)
  errors_per_sec = time_series.err_rate
  sessions_cur = time_series.scur
  queue_cur = time_series.qcur
  min_capacity = time_series.min_capacity
  max_capacity = time_series.max_capacity
  wanted_capacity = (min_capacity + max_capacity) / 2

  # Scale data arrays
  scale_time = time_series.scale_time
  nodes = time_series.nodes
  appservers = time_series.appservers
  pending = time_series.pending

  # Utilization data arrays
  utilization_time = time_series.utilization_time
  min_cpu_utilization = time_series.min_cpu_utilization
  avg_cpu_utilization = time_series.avg_cpu_utilization
  max_cpu_utilization = time_series.max_cpu_utilization
  min_memory_utilization = time_series.min_memory_utilization
  avg_memory_utilization = time_series.avg_memory_utilization
  max_memory_utilization = time_series.max_memory_utilization
  min_loadavg = time_series.min_loadavg
  avg_loadavg = time_series.avg_loadavg
  max_loadavg = time_series.max_loadavg


  pyplot.figure(1)

  # Plot general information about requests and capacity
  requests_plot = pyplot.subplot(321)
  requests_plot.set_xlim(start_time, end_time)
  requests_plot.set_ylim(0, 2600)
  requests_plot.set_xlabel("Time (in seconds)")
  requests_plot.plot(reqs_time, reqs_per_sec, color="#0101ee", label="Requests/sec.")
  requests_plot.plot(reqs_time, sessions_cur, linestyle="--", color="#0101aa", label="Current sessions")
  requests_plot.plot(reqs_time, queue_cur, linestyle=":", color="#bb0000", label="Current queue")
  requests_plot.plot(scale_time, wanted_capacity, color="#66aa66", label="Estimated sessions capacity")
  requests_plot.fill_between(scale_time, min_capacity, max_capacity, color="#99cc99", alpha=0.5)
  requests_plot.legend()

  # Plot errors rate
  errors_plot = pyplot.subplot(322)
  errors_plot.set_xlim(start_time, end_time)
  errors_plot.set_ylim(0, 100)
  errors_plot.plot(reqs_time, errors_per_sec, color="#dd0000", label="Errors/sec.")
  errors_plot.legend()

  # Plot CPU and Memory utilization
  utilization_plot = pyplot.subplot(323)
  utilization_plot.set_xlim(start_time, end_time)
  utilization_plot.set_ylim(0, 115)
  utilization_plot.plot(utilization_time, avg_cpu_utilization, color="#66aa66", label="average CPU")
  utilization_plot.fill_between(utilization_time, min_cpu_utilization, max_cpu_utilization, color="#99cc99", alpha=0.5, label="min/max CPU")
  utilization_plot.plot(utilization_time, avg_memory_utilization, color="#aa6666", label="average Memory")
  utilization_plot.fill_between(utilization_time, min_memory_utilization, max_memory_utilization, color="#cc9999", alpha=0.5, label="min/max Memory")
  utilization_plot.legend()

  # Plot loadavg
  loadavg_plot = pyplot.subplot(324)
  loadavg_plot.set_xlim(start_time, end_time)
  loadavg_plot.set_ylim(0, 8)
  loadavg_plot.plot(utilization_time, avg_loadavg, color="#6666aa", label="loadavg")
  loadavg_plot.fill_between(utilization_time, min_loadavg, max_loadavg, color="#9999cc", alpha=0.5, label="min/max loadavg")
  loadavg_plot.legend()

  # Plot number of appengine nodes
  machines_plot = pyplot.subplot(325)
  machines_plot.set_xlim(start_time, end_time)
  machines_plot.set_ylim(0, 27)
  machines_plot.plot(scale_time, nodes, color="#222222", label="nodes", linewidth=5, alpha=0.3)
  machines_plot.legend()

  # Plot number of started and pending appservers
  appservers_plot = pyplot.subplot(326)
  appservers_plot.set_xlim(start_time, end_time)
  appservers_plot.set_ylim(0, 280)
  appservers_plot.plot(scale_time, appservers, color="#00aa00", label="appservers", linewidth=3, alpha=0.6)
  appservers_plot.plot(scale_time, pending, color="#55aa55", linestyle=":", label="pending")
  appservers_plot.legend()

  pyplot.draw()
  pyplot.show()


def savitzky_golay(y, window_size, order, deriv=0, rate=1):
    r"""Smooth (and optionally differentiate) data with a Savitzky-Golay filter.
    The Savitzky-Golay filter removes high frequency noise from data.
    It has the advantage of preserving the original shape and
    features of the signal better than other types of filtering
    approaches, such as moving averages techniques.
    Parameters
    ----------
    y : array_like, shape (N,)
        the values of the time history of the signal.
    window_size : int
        the length of the window. Must be an odd integer number.
    order : int
        the order of the polynomial used in the filtering.
        Must be less then `window_size` - 1.
    deriv: int
        the order of the derivative to compute (default = 0 means only smoothing)
    Returns
    -------
    ys : ndarray, shape (N)
        the smoothed signal (or it's n-th derivative).
    Notes
    -----
    The Savitzky-Golay is a type of low-pass filter, particularly
    suited for smoothing noisy data. The main idea behind this
    approach is to make for each point a least-square fit with a
    polynomial of high order over a odd-sized window centered at
    the point.
    Examples
    --------
    t = np.linspace(-4, 4, 500)
    y = np.exp( -t**2 ) + np.random.normal(0, 0.05, t.shape)
    ysg = savitzky_golay(y, window_size=31, order=4)
    import matplotlib.pyplot as plt
    plt.plot(t, y, label='Noisy signal')
    plt.plot(t, np.exp(-t**2), 'k', lw=1.5, label='Original signal')
    plt.plot(t, ysg, 'r', label='Filtered signal')
    plt.legend()
    plt.show()
    References
    ----------
    .. [1] A. Savitzky, M. J. E. Golay, Smoothing and Differentiation of
       Data by Simplified Least Squares Procedures. Analytical
       Chemistry, 1964, 36 (8), pp 1627-1639.
    .. [2] Numerical Recipes 3rd Edition: The Art of Scientific Computing
       W.H. Press, S.A. Teukolsky, W.T. Vetterling, B.P. Flannery
       Cambridge University Press ISBN-13: 9780521880688
    """
    from math import factorial

    try:
        window_size = numpy.abs(numpy.int(window_size))
        order = numpy.abs(numpy.int(order))
    except ValueError, msg:
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")
    order_range = range(order+1)
    half_window = (window_size -1) // 2
    # precompute coefficients
    b = numpy.mat([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
    m = numpy.linalg.pinv(b).A[deriv] * rate**deriv * factorial(deriv)
    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - numpy.abs( y[1:half_window+1][::-1] - y[0] )
    lastvals = y[-1] + numpy.abs(y[-half_window-1:-1][::-1] - y[-1])
    y = numpy.concatenate((firstvals, y, lastvals))
    return numpy.convolve( m[::-1], y, mode='valid')


if __name__ == "__main__":
  main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
