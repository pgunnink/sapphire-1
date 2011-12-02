from __future__ import division

import tables
from itertools import combinations
import re
import csv

from pylab import *
from scipy.optimize import curve_fit
#from tikz_plot import tikz_2dhist

from scipy import integrate
from scipy.special import erf

USE_TEX = False


DETECTORS = [(0., 5.77, 'UD'), (0., 0., 'UD'), (-5., -2.89, 'LR'),
             (5., -2.89, 'LR')]

TIMING_ERROR = 4
#TIMING_ERROR = 7

# For matplotlib plots
if USE_TEX:
    rcParams['font.serif'] = 'Computer Modern'
    rcParams['font.sans-serif'] = 'Computer Modern'
    rcParams['font.family'] = 'sans-serif'
    rcParams['figure.figsize'] = [5 * x for x in (1, 2. / 3)]
    rcParams['figure.subplot.left'] = 0.125
    rcParams['figure.subplot.bottom'] = 0.125
    rcParams['font.size'] = 11
    rcParams['legend.fontsize'] = 'small'


class ReconstructedEvent(tables.IsDescription):
    r = tables.Float32Col()
    phi = tables.Float32Col()
    alpha = tables.Float32Col()
    t1 = tables.Float32Col()
    t2 = tables.Float32Col()
    t3 = tables.Float32Col()
    t4 = tables.Float32Col()
    n1 = tables.UInt16Col()
    n2 = tables.UInt16Col()
    n3 = tables.UInt16Col()
    n4 = tables.UInt16Col()
    sim_theta = tables.Float32Col()
    sim_phi = tables.Float32Col()
    r_theta = tables.Float32Col()
    r_phi = tables.Float32Col()
    D = tables.UInt16Col()
    size = tables.UInt8Col()
    bin = tables.Float32Col()
    bin_r = tables.BoolCol()


def reconstruct_angle(event, R=10):
    """Reconstruct angles from a single event"""

    dt1 = event['t1'] - event['t3']
    dt2 = event['t1'] - event['t4']

    return reconstruct_angle_dt(dt1, dt2, R)

def reconstruct_angle_dt(dt1, dt2, R=10):
    """Reconstruct angle given time differences"""

    c = 3.00e+8

    r1 = R
    r2 = R

    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    phi = arctan2((dt2 * r1 * cos(phi1) - dt1 * r2 * cos(phi2)),
                  (dt2 * r1 * sin(phi1) - dt1 * r2 * sin(phi2)) * -1)
    theta1 = arcsin(c * dt1 * 1e-9 / (r1 * cos(phi - phi1)))
    theta2 = arcsin(c * dt2 * 1e-9 / (r2 * cos(phi - phi2)))

    e1 = sqrt(rel_theta1_errorsq(theta1, phi, phi1, phi2, R, R))
    e2 = sqrt(rel_theta2_errorsq(theta2, phi, phi1, phi2, R, R))

    theta_wgt = (1 / e1 * theta1 + 1 / e2 * theta2) / (1 / e1 + 1 / e2)

    return theta_wgt, phi

def calc_phi(s1, s2):
    """Calculate angle between detectors (phi1, phi2)"""

    x1, y1 = DETECTORS[s1 - 1][:2]
    x2, y2 = DETECTORS[s2 - 1][:2]

    return arctan2((y2 - y1), (x2 - x1))

def rel_phi_errorsq(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    tanphi = tan(phi)
    sinphi1 = sin(phi1)
    cosphi1 = cos(phi1)
    sinphi2 = sin(phi2)
    cosphi2 = cos(phi2)

    den = ((1 + tanphi ** 2) ** 2 * r1 ** 2 * r2 ** 2 * sin(theta) ** 2
       * (sinphi1 * cos(phi - phi2) - sinphi2 * cos(phi - phi1)) ** 2
       / c ** 2)

    A = (r1 ** 2 * sinphi1 ** 2
         + r2 ** 2 * sinphi2 ** 2
         - r1 * r2 * sinphi1 * sinphi2)
    B = (2 * r1 ** 2 * sinphi1 * cosphi1
         + 2 * r2 ** 2 * sinphi2 * cosphi2
         - r1 * r2 * sinphi2 * cosphi1
         - r1 * r2 * sinphi1 * cosphi2)
    C = (r1 ** 2 * cosphi1 ** 2
         + r2 ** 2 * cosphi2 ** 2
         - r1 * r2 * cosphi1 * cosphi2)

    return 2 * (A * tanphi ** 2 + B * tanphi + C) / den

def dphi_dt0(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    tanphi = tan(phi)
    sinphi1 = sin(phi1)
    cosphi1 = cos(phi1)
    sinphi2 = sin(phi2)
    cosphi2 = cos(phi2)

    den = ((1 + tanphi ** 2) * r1 * r2 * sin(theta)
           * (sinphi2 * cos(phi - phi1) - sinphi1 * cos(phi - phi2))
           / c)
    num = (r2 * cosphi2 - r1 * cosphi1
           + tanphi * (r2 * sinphi2 - r1 * sinphi1))

    return num / den

def dphi_dt1(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    tanphi = tan(phi)
    sinphi1 = sin(phi1)
    cosphi1 = cos(phi1)
    sinphi2 = sin(phi2)
    cosphi2 = cos(phi2)

    den = ((1 + tanphi ** 2) * r1 * r2 * sin(theta)
           * (sinphi2 * cos(phi - phi1) - sinphi1 * cos(phi - phi2))
           / c)
    num = -r2 * (sinphi2 * tanphi + cosphi2)

    return num / den

def dphi_dt2(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    tanphi = tan(phi)
    sinphi1 = sin(phi1)
    cosphi1 = cos(phi1)
    sinphi2 = sin(phi2)
    cosphi2 = cos(phi2)

    den = ((1 + tanphi ** 2) * r1 * r2 * sin(theta)
           * (sinphi2 * cos(phi - phi1) - sinphi1 * cos(phi - phi2))
           / c)
    num = r1 * (sinphi1 * tanphi + cosphi1)

    return num / den

def rel_theta_errorsq(theta, phi, phi1, phi2, r1=10, r2=10):
    e1 = rel_theta1_errorsq(theta, phi, phi1, phi2, r1, r2)
    e2 = rel_theta2_errorsq(theta, phi, phi1, phi2, r1, r2)

    #return minimum(e1, e2)
    return e1

def rel_theta1_errorsq(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    sintheta = sin(theta)
    sinphiphi1 = sin(phi - phi1)

    den = (1 - sintheta ** 2) * r1 ** 2 * cos(phi - phi1) ** 2

    A = (r1 ** 2 * sinphiphi1 ** 2
         * rel_phi_errorsq(theta, phi, phi1, phi2, r1, r2))
    B = (r1 * c * sinphiphi1
         * (dphi_dt0(theta, phi, phi1, phi2, r1, r2)
            - dphi_dt1(theta, phi, phi1, phi2, r1, r2)))
    C = 2 * c ** 2

    errsq = (A * sintheta ** 2 - 2 * B * sintheta + C) / den

    return where(isnan(errsq), inf, errsq)

def rel_theta2_errorsq(theta, phi, phi1, phi2, r1=10, r2=10):
    # speed of light in m / ns
    c = .3

    sintheta = sin(theta)
    sinphiphi2 = sin(phi - phi2)

    den = (1 - sintheta ** 2) * r2 ** 2 * cos(phi - phi2) ** 2

    A = (r2 ** 2 * sinphiphi2 ** 2
         * rel_phi_errorsq(theta, phi, phi1, phi2, r1, r2))
    B = (r2 * c * sinphiphi2
         * (dphi_dt0(theta, phi, phi1, phi2, r1, r2)
            - dphi_dt2(theta, phi, phi1, phi2, r1, r2)))
    C = 2 * c ** 2

    errsq = (A * sintheta ** 2 - 2 * B * sintheta + C) / den

    return where(isnan(errsq), inf, errsq)

def do_full_reconstruction(data, tablename):
    """Do a reconstruction of all simulated data and store results"""

    try:
        data.createGroup('/', 'reconstructions', "Angle reconstructions")
    except tables.NodeError:
        pass

    try:
        data.removeNode('/reconstructions', tablename)
    except tables.NoSuchNodeError:
        pass

    table = data.createTable('/reconstructions', tablename,
                             ReconstructedEvent, "Reconstruction data")

    kwargs = dict(data=data, dest=table, D=1)
    reconstruct_angles(tablename='zenith_0', THETA=0, **kwargs)
    reconstruct_angles(tablename='zenith_5', THETA=deg2rad(5), **kwargs)
    reconstruct_angles(tablename='zenith_22_5', THETA=pi / 8, **kwargs)
    reconstruct_angles(tablename='zenith_35', THETA=deg2rad(35), **kwargs)

    # SPECIALS
    # Station sizes
    reconstruct_angles(tablename='zenith_22_5_size5', THETA=pi / 8, **kwargs)
    reconstruct_angles(tablename='zenith_22_5_size20', THETA=pi / 8, **kwargs)

    # SPECIALS
    # Binnings
    kwargs = dict(data=data, tablename='zenith_22_5', dest=table,
                  THETA=pi / 8, D=1)
    kwargs['randomize_binning'] = False
    reconstruct_angles(binning=1, **kwargs)
    reconstruct_angles(binning=2.5, **kwargs)
    reconstruct_angles(binning=5, **kwargs)
    kwargs['randomize_binning'] = True
    reconstruct_angles(binning=1, **kwargs)
    reconstruct_angles(binning=2.5, **kwargs)
    reconstruct_angles(binning=5, **kwargs)

def reconstruct_angles(data, tablename, dest, THETA, D, binning=False,
                       randomize_binning=False, N=None):
    """Reconstruct angles from simulation for minimum particle density"""

    match = re.search('_size([0-9]+)', tablename)
    if match:
        R = int(match.group(1))
    else:
        R = 10

    shower_group = data.getNode('/simulations/E_1PeV', tablename)

    for shower in data.listNodes(shower_group):
        shower_table = shower.observables
        coincidence_table = shower.coincidences
        dst_row = dest.row
        for event, coincidence in zip(shower_table[:N], coincidence_table[:N]):
            assert event['id'] == coincidence['id']
            if min(event['n1'], event['n3'], event['n4']) >= D:
                # Do we need to bin timing data?
                if binning is not False:
                    event['t1'] = floor(event['t1'] / binning) * binning
                    event['t2'] = floor(event['t2'] / binning) * binning
                    event['t3'] = floor(event['t3'] / binning) * binning
                    event['t4'] = floor(event['t4'] / binning) * binning
                    # Do we need to randomize inside a bin?
                    if randomize_binning is True:
                        event['t1'] += uniform(0, binning)
                        event['t2'] += uniform(0, binning)
                        event['t3'] += uniform(0, binning)
                        event['t4'] += uniform(0, binning)

                theta, phi = reconstruct_angle(event, R)

                alpha = event['alpha']

                if not isnan(theta) and not isnan(phi):
#                    ang_dist = arccos(sin(theta) * sin(THETA) *
#                                      cos(phi - -alpha) + cos(theta) *
#                                      cos(THETA))

                    dst_row['r'] = coincidence['r']
                    dst_row['phi'] = coincidence['phi']
                    dst_row['alpha'] = event['alpha']
                    dst_row['t1'] = event['t1']
                    dst_row['t2'] = event['t2']
                    dst_row['t3'] = event['t3']
                    dst_row['t4'] = event['t4']
                    dst_row['n1'] = event['n1']
                    dst_row['n2'] = event['n2']
                    dst_row['n3'] = event['n3']
                    dst_row['n4'] = event['n4']
                    dst_row['sim_theta'] = THETA
                    dst_row['sim_phi'] = coincidence['alpha']
                    dst_row['r_theta'] = theta
                    dst_row['r_phi'] = phi
                    dst_row['D'] = min(event['n1'], event['n3'], event['n4'])
                    dst_row['size'] = R
                    if binning is False:
                        bin_size = 0
                    else:
                        bin_size = binning
                    dst_row['bin'] = bin_size
                    dst_row['bin_r'] = randomize_binning
                    dst_row.append()
    dest.flush()

def do_reconstruction_plots(data, tablename):
    """Make plots based upon earlier reconstructions"""

    table = data.getNode('/reconstructions', tablename)

    plot_uncertainty_mip(table)
    plot_uncertainty_zenith(table)
    plot_uncertainty_size(table)
    plot_uncertainty_binsize(table)

    plot_phi_reconstruction_results_for_MIP(table, 1)
    plot_phi_reconstruction_results_for_MIP(table, 2)
    boxplot_theta_reconstruction_results_for_MIP(table, 1)
    boxplot_theta_reconstruction_results_for_MIP(table, 2)
    boxplot_phi_reconstruction_results_for_MIP(table, 1)
    boxplot_phi_reconstruction_results_for_MIP(table, 2)
    boxplot_arrival_times(table, 1)
    boxplot_arrival_times(table, 2)
    boxplot_core_distances_for_mips(table)
    plot_reconstruction_efficiency_vs_R_for_angles(1)
    plot_reconstruction_efficiency_vs_R_for_angles(2)

def plot_uncertainty_mip(table):
    # constants for uncertainty estimation
    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    figure()
    rcParams['text.usetex'] = False
    x, y, y2 = [], [], []
    for D in range(1, 6):
        x.append(D)
        events = table.readWhere(
            '(D==%d) & (sim_theta==%.40f) & (size==10) & (bin==0) & '
            '(0 < r) & (r <= 100)' % (D, float32(pi / 8)))
        print len(events),
        errors = events['sim_theta'] - events['r_theta']
        # Make sure -pi < errors < pi
        errors = (errors + pi) % (2 * pi) - pi
        errors2 = events['sim_phi'] - events['r_phi']
        # Make sure -pi < errors2 < pi
        errors2 = (errors2 + pi) % (2 * pi) - pi
        y.append(std(errors))
        y2.append(std(errors2))
    plot(x, rad2deg(y), '^', label="Theta")
    plot(x, rad2deg(y2), 'v', label="Phi")
    print
    print "mip: D, theta_std, phi_std"
    for u, v, w in zip(x, y, y2):
        print u, v, w
    print
    # Uncertainty estimate
    x = linspace(1, 5, 50)
    phis = linspace(-pi, pi, 50)
    phi_errsq = mean(rel_phi_errorsq(pi / 8, phis, phi1, phi2))
    theta_errsq = mean(rel_theta_errorsq(pi / 8, phis, phi1, phi2))
    y = TIMING_ERROR * std_t(x) * sqrt(phi_errsq)
    y2 = TIMING_ERROR * std_t(x) * sqrt(theta_errsq)
    plot(x, rad2deg(y), label="Estimate Phi")
    plot(x, rad2deg(y2), label="Estimate Theta")
    # Labels etc.
    xlabel("Minimum number of particles")
    ylabel("Uncertainty in angle reconstruction (deg)")
    title(r"$\theta = 22.5^\circ$")
    legend(numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-MIP.pdf')
    print

def plot_uncertainty_zenith(table):
    # constants for uncertainty estimation
    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    figure()
    rcParams['text.usetex'] = False
    x, y, y2 = [], [], []
    global MYT
    MYT = []
    for THETA in [0, deg2rad(5), pi / 8, deg2rad(35)]:
        x.append(THETA)
        events = table.readWhere(
            '(D==2) & (sim_theta==%.40f) & (size==10) & (bin==0)' %
            float32(THETA))
        MYT.append((events['t1'], events['t3'], events['t4']))
        print rad2deg(THETA), len(events),
        errors = events['sim_theta'] - events['r_theta']
        # Make sure -pi < errors < pi
        errors = (errors + pi) % (2 * pi) - pi
        errors2 = events['sim_phi'] - events['r_phi']
        # Make sure -pi < errors2 < pi
        errors2 = (errors2 + pi) % (2 * pi) - pi
        y.append(std(errors))
        y2.append(std(errors2))
    plot(rad2deg(x), rad2deg(y), '^', label="Theta")
    # Azimuthal angle undefined for zenith = 0
    plot(rad2deg(x[1:]), rad2deg(y2[1:]), 'v', label="Phi")
    print
    print "zenith: theta, theta_std, phi_std"
    for u, v, w in zip(x, y, y2):
        print u, v, w
    print
    # Uncertainty estimate
    x = linspace(0, deg2rad(35), 50)
    phis = linspace(-pi, pi, 50)
    y, y2, y3 = [], [], []
    for t in x:
        y.append(mean(rel_phi_errorsq(t, phis, phi1, phi2)))
        y3.append(mean(rel_phi_errorsq(t, phis, phi1, phi2)) * sin(t) ** 2)
        y2.append(mean(rel_theta_errorsq(t, phis, phi1, phi2)))
    y = TIMING_ERROR * sqrt(array(y))
    y3 = TIMING_ERROR * sqrt(array(y3))
    y2 = TIMING_ERROR * sqrt(array(y2))
    plot(rad2deg(x), rad2deg(y), label="Estimate Phi")
    plot(rad2deg(x), rad2deg(y3), label="Estimate Phi * sin(Theta)")
    plot(rad2deg(x), rad2deg(y2), label="Estimate Theta")
    # Labels etc.
    xlabel("Shower zenith angle (degrees)")
    ylabel("Uncertainty in angle reconstruction (deg)")
    title(r"$N_{MIP} = 2$")
    ylim(0, 100)
    legend(numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-zenith.pdf')
    print

def plot_uncertainty_phi(table):
    # constants for uncertainty estimation
    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    figure()
    rcParams['text.usetex'] = False
    # Uncertainty estimate
    x = linspace(0, deg2rad(360), 50)
    y, y2 = [], []
    for p in x:
        y.append(rel_phi_errorsq(pi / 8, p, phi1, phi2))
        y2.append(rel_theta_errorsq(pi / 8, p, phi1, phi2))
    y = TIMING_ERROR * sqrt(array(y))
    y2 = TIMING_ERROR * sqrt(array(y2))
    plot(rad2deg(x), rad2deg(y), label="Estimate Phi")
    plot(rad2deg(x), rad2deg(y2), label="Estimate Theta")
    # Labels etc.
    xlabel("Shower azimuth angle (degrees)")
    ylabel("Uncertainty in angle reconstruction (deg)")
    title(r"$\theta = 22.5^\circ, N_{MIP} = 2$")
    legend(numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-phi.pdf')
    print

def plot_uncertainty_size(table):
    # constants for uncertainty estimation
    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    figure()
    rcParams['text.usetex'] = False
    x, y, y2 = [], [], []
    for size in [5, 10, 20]:
        x.append(size)
        events = table.readWhere(
            '(D==2) & (sim_theta==%.40f) & (size==%d) & (bin==0)' %
            (float32(pi / 8), size))
        print len(events),
        errors = events['sim_theta'] - events['r_theta']
        # Make sure -pi < errors < pi
        errors = (errors + pi) % (2 * pi) - pi
        errors2 = events['sim_phi'] - events['r_phi']
        # Make sure -pi < errors2 < pi
        errors2 = (errors2 + pi) % (2 * pi) - pi
        y.append(std(errors))
        y2.append(std(errors2))
    plot(x, rad2deg(y), '^', label="Theta")
    plot(x, rad2deg(y2), 'v', label="Phi")
    print
    print "stationsize: size, theta_std, phi_std"
    for u, v, w in zip(x, y, y2):
        print u, v, w
    print
    # Uncertainty estimate
    x = linspace(5, 20, 50)
    phis = linspace(-pi, pi, 50)
    y, y2 = [], []
    for s in x:
        y.append(mean(rel_phi_errorsq(pi / 8, phis, phi1, phi2, r1=s, r2=s)))
        y2.append(mean(rel_theta_errorsq(pi / 8, phis, phi1, phi2, r1=s, r2=s)))
    y = TIMING_ERROR * sqrt(array(y))
    y2 = TIMING_ERROR * sqrt(array(y2))
    plot(x, rad2deg(y), label="Estimate Phi")
    plot(x, rad2deg(y2), label="Estimate Theta")
    # Labels etc.
    xlabel("Station size (m)")
    ylabel("Uncertainty in angle reconstruction (deg)")
    title(r"$\theta = 22.5^\circ, N_{MIP} = 2$")
    legend(numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-size.pdf')
    print

def plot_uncertainty_binsize(table):
    # constants for uncertainty estimation
    phi1 = calc_phi(1, 3)
    phi2 = calc_phi(1, 4)

    figure()
    rcParams['text.usetex'] = False
    x, y, y2 = [], [], []
    for bin_size in [0, 1, 2.5, 5]:
        if bin_size == 0:
            is_randomized = False
        else:
            is_randomized = True
        x.append(bin_size)
        events = table.readWhere(
            '(D==2) & (sim_theta==%.40f) & (size==10) & (bin==%.40f) & '
            '(bin_r==%s)' %
            (float32(pi / 8), bin_size, is_randomized))
        print len(events),
        errors = events['sim_theta'] - events['r_theta']
        # Make sure -pi < errors < pi
        errors = (errors + pi) % (2 * pi) - pi
        errors2 = events['sim_phi'] - events['r_phi']
        # Make sure -pi < errors2 < pi
        errors2 = (errors2 + pi) % (2 * pi) - pi
        y.append(std(errors))
        y2.append(std(errors2))
    plot(x, rad2deg(y), '^', label="Theta")
    plot(x, rad2deg(y2), 'v', label="Phi")
    print
    print "binsize: size, theta_std, phi_std"
    for u, v, w in zip(x, y, y2):
        print u, v, w
    print
    # Uncertainty estimate
    x = linspace(0, 5, 50)
    phis = linspace(-pi, pi, 50)
    y, y2 = [], []
    phi_errorsq = mean(rel_phi_errorsq(pi / 8, phis, phi1, phi2))
    theta_errorsq = mean(rel_theta_errorsq(pi / 8, phis, phi1, phi2))
    for t in x:
        y.append(sqrt((TIMING_ERROR ** 2 + t ** 2 / 12) * phi_errorsq))
        y2.append(sqrt((TIMING_ERROR ** 2 + t ** 2 / 12) * theta_errorsq))
    y = array(y)
    y2 = array(y2)
    plot(x, rad2deg(y), label="Estimate Phi")
    plot(x, rad2deg(y2), label="Estimate Theta")
    # Labels etc.
    xlabel("Bin size (ns)")
    ylabel("Uncertainty in angle reconstruction (deg)")
    title(r"$\theta = 22.5^\circ, N_{MIP} = 2$")
    legend(loc='best', numpoints=1)
    ylim(ymin=0)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-binsize.pdf')
    print

# Time of first hit pamflet functions
Q = lambda t, n: ((.5 * (1 - erf(t / sqrt(2)))) ** (n - 1)
                  * exp(-.5 * t ** 2) / sqrt(2 * pi))

expv_t = vectorize(lambda n: integrate.quad(lambda t: t * Q(t, n)
                                                      / n ** -1,
                                            - inf, +inf))
expv_tv = lambda n: expv_t(n)[0]
expv_tsq = vectorize(lambda n: integrate.quad(lambda t: t ** 2 * Q(t, n)
                                                        / n ** -1,
                                              - inf, +inf))
expv_tsqv = lambda n: expv_tsq(n)[0]

std_t = lambda n: sqrt(expv_tsqv(n) - expv_tv(n) ** 2)

def plot_shower_front_timings(data, tablename):
    table = data.getNode('/analysis', tablename)

    figure()
    rcParams['text.usetex'] = False
    for R0, R1 in [(0, 4), (4, 20), (20, 40), (40, 80)]:
        events = table.readWhere('(n1==2) & (n2==2) & (%d <= r) & (r < %d)'
                                 % (R0, R1))
        if len(events):
            hist([u for u in events['t1'] - events['t2'] if not isnan(u)],
                 bins=linspace(-50, 50, 100), histtype='step', normed=True,
                 label="$%d <= R < %d$" % (R0, R1))
    xlabel("Arrival time difference (ns)")
    ylabel("Count")
    title(r"Shower front thickness ($\theta = %s^\circ$)" %
          tablename.replace('zenith_', ''))
    legend()
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-shower-front-timings-%s.pdf' % tablename)

def plot_shower_front_density(data, tablename):
    table = data.getNode('/analysis', tablename)

    figure()
    rcParams['text.usetex'] = False
    for R0, R1 in [(0, 4), (4, 20), (20, 40), (40, 80)]:
        events = table.readWhere('(%d <= r) & (r < %d)' % (R0, R1))
        hist(events['n1'],
             bins=arange(-.5, 5.5), histtype='step',
             label="$%d <= R < %d$" % (R0, R1))
    xlabel("Number of particles per scintillator")
    ylabel("Count")
    title(r"Shower front density ($\theta = %s^\circ$)" %
          tablename.replace('zenith_', ''))
    legend()
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-shower-front-density-%s.pdf' % tablename)

def plot_zenith_core_dists(data):
    figure()
    rcParams['text.usetex'] = False
    for t in ['zenith_0', 'zenith_5', 'zenith_23', 'zenith_35']:
        table = data.getNode('/analysis', t)
        events = table.readWhere('(n1==2) & (n3==2) & (n4==2)')
        hist(events['r'], bins=linspace(0, 100, 50), histtype='step',
             label=r'$\theta = %s^\circ$' % t.replace('zenith_', ''))
    xlabel("Core distance (m)")
    ylabel("Count")
    title("Core distances ($N_{MIP} = 2$)")
    legend()
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-zenith-core-dists.pdf')

def plot_mip_core_dists(data, tablename):
    table = data.getNode('/analysis', tablename)
    figure()
    rcParams['text.usetex'] = False
    x, y = [], []
    for N in range(1, 6):
        events = table.readWhere('(n1==%d) & (n3==%d) & (n4==%d)' % (N, N, N))
        x.append(N)
        y.append(mean(events['r']))
        hist(events['r'], bins=linspace(0, 100, 50), histtype='step',
             label='%d MIP' % N)
    xlabel("Core distance (m)")
    ylabel("Count")
    title(r"Core distances ($\theta = 22.5^\circ$)")
    legend()
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-mip-core-dists-%s.pdf' %
            tablename.replace('_', '-'))

def plot_mip_core_dists_mean(table):
    figure()
    rcParams['text.usetex'] = False
    for THETA in [0, deg2rad(5), pi / 8, deg2rad(35)]:
        x, y, yerr = [], [], []
        for N in range(1, 6):
            events = table.readWhere(
                '(D==%d) & (sim_theta==%.40f) & (size==10) & (bin==0)' %
                (N, float32(THETA)))
            x.append(N)
            y.append(mean(events['r']))
            yerr.append(std(events['r']))
        plot(x, y, '^-', label=r"$\theta = %.1f^\circ$" % rad2deg(THETA))
    print "zenith: theta, r_mean, r_std"
    for u, v, w in zip(x, y, yerr):
        print u, v, w
    print
    # Labels etc.
    xlabel("Number of particles")
    ylabel("Core distance (m)")
    legend(numpoints=1)
    xlim(.5, 5.5)
    ylim(ymin=0)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-mip_core_dists_mean.pdf')
    print

    figure()
    rcParams['text.usetex'] = False
    THETA = pi / 8
    x, y, yerr = [], [], []
    for N in range(1, 6):
        events = table.readWhere(
            '(D==%d) & (sim_theta==%.40f) & (size==10) & (bin==0)' %
            (N, float32(THETA)))
        x.append(N)
        y.append(mean(events['r']))
        yerr.append(std(events['r']))
    plot(x, y, '^-', label=r"$\theta = %.1f^\circ$" % rad2deg(THETA))
    print "zenith: theta, r_mean, r_std"
    for u, v, w in zip(x, y, yerr):
        print u, v, w
    print
    # Labels etc.
    xlabel("Number of particles")
    ylabel("Core distance (m)")
    title(r"$\theta = %.1f^\circ$" % rad2deg(THETA))
    xlim(.5, 5.5)
    ylim(ymin=0)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-mip_core_dists_mean2.pdf')
    print

def plot_sim_shower_timings(datafile):
    data = tables.openFile(datafile, 'r')

    global DT

    figure()
    rcParams['text.usetex'] = False
    x, y, y2 = [], [], []
    for n in data.root._v_children:
        t = data.getNode('/', n)
        events = t.read()
        x.append(mean(events['R']))
        y.append(std(events['T'] - events['t']))
        DT = events['T'] - events['t']
        dts = sorted(abs(events['T'] - events['t']))
        err = dts[2 * len(dts) / 3]
        y2.append(err)
    plot(x, y, '^', label="Std. dev.")
    plot(x, y2, '^', label="cont. 68 %")
    xlabel("Core distance (m)")
    ylabel("Uncertainty in time difference (ns)")
    title(r"$\theta = 0^\circ$")
    legend(loc='best')
    ylim(ymin=0)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-sim-shower-timings.pdf')

def plot_uncertainty_core_dist_phi(table):
    figure()
    rcParams['text.usetex'] = False
    THETA = pi / 8
    bins = linspace(0, 80, 6)
    for N in range(1, 6):
        events = table.readWhere(
            '(D==%d) & (sim_theta==%.40f) & (size==10) & (bin==0)' %
            (N, float32(THETA)))
        x, y, yerr, l = [], [], [], []
        for r0, r1 in zip(bins[:-1], bins[1:]):
            e = events.compress((r0 <= events['r']) & (events['r'] < r1))
            if len(e) > 10:
                x.append(mean([r0, r1]))
                y.append(mean(e['sim_phi'] - e['r_phi']))
                yerr.append(std(e['sim_phi'] - e['r_phi']))
                l.append(len(e))
        print "core_dist_mip_unc: core, phi_e_mean, phi_e_std, len"
        for u, v, w, i in zip(x, y, yerr, l):
            print u, v, w, i
        print
        plot(x, rad2deg(yerr), '^-', label="%d MIP" % N)
    # Labels etc.
    xlabel("Core distance (m)")
    ylabel("Uncertainty phi (deg)")
    title(r"$\theta = 22.5^\circ$")
    legend(loc='best', numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-core-dist-phi.pdf')
    print

def plot_uncertainty_core_dist_theta(table):
    figure()
    rcParams['text.usetex'] = False
    THETA = pi / 8
    bins = linspace(0, 80, 6)
    for N in range(1, 6):
        events = table.readWhere(
            '(D==%d) & (sim_theta==%.40f) & (size==10) & (bin==0)' %
            (N, float32(THETA)))
        x, y, yerr, l = [], [], [], []
        for r0, r1 in zip(bins[:-1], bins[1:]):
            e = events.compress((r0 <= events['r']) & (events['r'] < r1))
            if len(e) > 10:
                x.append(mean([r0, r1]))
                y.append(mean(e['sim_theta'] - e['r_theta']))
                yerr.append(std(e['sim_theta'] - e['r_theta']))
                l.append(len(e))
        print "core_dist_mip_unc: core, theta_e_mean, theta_e_std, len"
        for u, v, w, i in zip(x, y, yerr, l):
            print u, v, w, i
        print
        plot(x, rad2deg(yerr), '^-', label="%d MIP" % N)
    # Labels etc.
    xlabel("Core distance (m)")
    ylabel("Uncertainty theta (deg)")
    title(r"$\theta = 22.5^\circ$")
    legend(loc='best', numpoints=1)
    if USE_TEX:
        rcParams['text.usetex'] = True
    savefig('plots/auto-results-core-dist-theta.pdf')
    print

def plot_phi_reconstruction_results_for_MIP(table, N):
    min_theta = 1
    query = '(D>=%d) & (size==10) & (bin==0) & (sim_theta > %.5f)' % \
            (N, deg2rad(min_theta))

    events = table.readWhere(query)
    sim_phi = events['sim_phi']
    r_phi = events['r_phi']

    figure()
    plot_2d_histogram(rad2deg(sim_phi), rad2deg(r_phi), 180)
    xlabel(r"$\phi_{simulated}$")
    ylabel(r"$\phi_{reconstructed}$")
    title(r"$N_{MIP} \geq %d, \quad \theta > 0^\circ$" % N)

    savefig("plots/auto-results-phi-reconstruction-%d.pdf" % N)

def boxplot_theta_reconstruction_results_for_MIP(table, N):
    figure()
    query = '(D>=%d) & (size==10) & (bin==0)' % N

    angles = [0, 5, 22.5, 35]
    r_dtheta = []
    for angle in angles:
        low, high = deg2rad(angle - 1), deg2rad(angle + 1)
        sel_query = query + '& (low < sim_theta) & (sim_theta < high)'
        sel = table.readWhere(sel_query)
        r_dtheta.append(rad2deg(sel[:]['r_theta'] - sel[:]['sim_theta']))

    boxplot(r_dtheta, sym='')
    xticks(range(1, len(angles) + 1), [str(u) for u in angles])

    xlabel(r"$\theta_{simulated}$")
    ylabel(r"$\theta_{reconstructed} - \theta_{simulated}$")
    title(r"$N_{MIP} \geq %d$" % N)

    axhline(0)
    ylim(-20, 20)

    savefig("plots/auto-results-theta-reconstruction-%d.pdf" % N)

def boxplot_phi_reconstruction_results_for_MIP(table, N):
    figure()
    min_theta = 1
    query = '(D>=%d) & (size==10) & (bin==0) & (sim_theta > %.5f)' % \
            (N, deg2rad(min_theta))

    bin_edges = linspace(-180, 180, 18)
    x, r_dphi = [], []
    for low, high in zip(bin_edges[:-1], bin_edges[1:]):
        rad_low = deg2rad(low)
        rad_high = deg2rad(high)
        sel_query = query + '& (rad_low < sim_phi) & (sim_phi < rad_high)'
        sel = table.readWhere(sel_query)
        dphi = sel[:]['r_phi'] - sel[:]['sim_phi']
        dphi = (dphi + pi) % (2 * pi) - pi
        r_dphi.append(rad2deg(dphi))
        x.append((low + high) / 2)

    boxplot(r_dphi, positions=x, widths=.7 * (high - low), sym='')

    xlabel(r"$\phi_{simulated}$")
    ylabel(r"$\phi_{reconstructed} - \phi_{simulated}$")
    title(r"$N_{MIP} \geq %d, \quad \theta > 0^\circ$" % N)

    xticks(linspace(-180, 180, 9))
    axhline(0)

    savefig("plots/auto-results-phi-reconstruction-box-%d.pdf" % N)

def boxplot_arrival_times(table, N):
    figure()
    query = '(D>=%d) & (size==10) & (bin==0) & (sim_theta == 0)' % N

    bin_edges = linspace(0, 100, 10)
    x, arrival_times = [], []
    for low, high in zip(bin_edges[:-1], bin_edges[1:]):
        sel_query = query + '& (low <= r) & (r < high)'
        sel = table.readWhere(sel_query)
        t2 = sel[:]['t2']
        arrival_times.append(t2.compress(t2 > -999))
        x.append((low + high) / 2)

    boxplot(arrival_times, positions=x, widths=.7 * (high - low), sym='')

    xlabel("Core distance [m]")
    ylabel("Arrival time [ns]")
    title(r"$N_{MIP} \geq %d, \quad \theta = 0^\circ$" % N)

    xticks(arange(0, 100.5, 10))

    savefig("plots/auto-results-boxplot-arrival-times-%d.pdf" % N)

def boxplot_core_distances_for_mips(table):
    query = ('(size==10) & (bin==0) & (sim_theta == %.40f)' %
             float32(deg2rad(22.5)))

    r_list = []
    for D in range(1, 5):
        sel_query = query + '& (D == %d)' % D
        sel = table.readWhere(sel_query)
        r = sel[:]['r']
        r_list.append(r)

    figure()
    boxplot(r_list)
    xticks(range(1, 5))
    xlabel("Minimum number of particles")
    ylabel("Core distance [m]")
    title(r"$\theta = 22.5^\circ$")

    savefig("plots/auto-results-boxplot-core-distances-for-mips.pdf")

def plot_reconstruction_efficiency_vs_R_for_angles(N):
    figure()

    bin_edges = linspace(0, 100, 20)
    x = (bin_edges[:-1] + bin_edges[1:]) / 2.

    for angle in [0, 5, 22.5, 35]:
        angle_str = str(angle).replace('.', '_')
        shower_group = '/simulations/E_1PeV/zenith_%s' % angle_str

        efficiencies = []
        for low, high in zip(bin_edges[:-1], bin_edges[1:]):
            shower_results = []
            for shower in data.listNodes(shower_group):
                sel_query = '(low <= r) & (r < high)'
                coinc_sel = shower.coincidences.readWhere(sel_query)
                ids = coinc_sel['id']
                obs_sel = shower.observables.readCoordinates(ids)
                assert (obs_sel['id'] == ids).all()

                o = obs_sel
                sel = obs_sel.compress((o['n1'] >= N) & (o['n3'] >= N) &
                                       (o['n4'] >= N))
                shower_results.append(len(sel) / len(obs_sel))
            efficiencies.append(mean(shower_results))

        plot(x, efficiencies, label=r'$\theta = %s^\circ$' % angle)

    xlabel("Core distance [m]")
    ylabel("Reconstruction efficiency")
    title(r"$N_{MIP} \geq %d$" % N)
    legend()

    savefig('plots/plot_reconstruction_efficiency_vs_R_for_angles-%dMIP.pdf' % N)

def plot_2d_histogram(x, y, bins):
    H, xedges, yedges = histogram2d(x, y, bins)
    imshow(H.T, extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
           origin='lower left', interpolation='lanczos', aspect='auto')
    colorbar()


if __name__ == '__main__':
    # invalid values in arcsin will be ignored (nan handles the situation
    # quite well)
    np.seterr(invalid='ignore')

    try:
        data
    except NameError:
        data = tables.openFile('master.h5', 'a')

    if '/reconstructions/full' not in data:
        print "Reconstructing shower direction..."
        do_full_reconstruction(data, 'full')
    else:
        print "Skipping reconstruction!"

    do_reconstruction_plots(data, 'full')