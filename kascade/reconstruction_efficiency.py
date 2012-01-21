import tables
import numpy as np
import pylab as plt
from scipy import optimize

from sapphire.analysis import landau


RANGE_MAX = 40000
N_BINS = 400


class ReconstructionEfficiency(object):
    def __init__(self, data):
        self.data = data
        self.scintillator = landau.Scintillator()

    def main(self):
        self.plot_landau_fit()

    def plot_landau_fit(self):
        global x, n, bins, p_gamma, p_landau

        events = self.data.root.hisparc.cluster_kascade.station_601.events
        ph0 = events.col('integrals')[:, 0]

        bins = np.linspace(0, RANGE_MAX, N_BINS + 1)
        n, bins = np.histogram(ph0, bins=bins)
        x = (bins[:-1] + bins[1:]) / 2

        p_gamma = self.fit_gammas_to_data(x, n)
        p_landau = self.fit_conv_landau_to_data(x, n - self.gamma_func(x, *p_gamma))
        p_gamma, p_landau = self.fit_complete(x, n, p_gamma, p_landau)

        clf()
        plt.plot(x, n)
        self.plot_landau_and_gamma(x, p_gamma, p_landau)
        plt.plot(x, n - self.gamma_func(x, *p_gamma))
        plt.yscale('log')
        plt.xlim(xmin=0)
        plt.ylim(ymin=1e2)

    def plot_landau_and_gamma(self, x, p_gamma, p_landau):
        gammas = self.gamma_func(x, *p_gamma)
        plt.plot(x, gammas)

        nx = np.linspace(-RANGE_MAX, RANGE_MAX, N_BINS * 2 + 1)
        nlandaus = self.scintillator.conv_landau(nx, *p_landau)
        landaus = np.interp(x, nx, nlandaus)
        plt.plot(x, landaus)

        plt.plot(x, gammas + landaus)


    def fit_gammas_to_data(self, x, y):
        condition = (500 <= x) & (x < 2000)
        x_trunc = x.compress(condition)
        y_trunc = y.compress(condition)
        popt, pcov = optimize.curve_fit(self.gamma_func, x_trunc, y_trunc, p0=(1., 1.))
        return popt

    def gamma_func(self, x, N, a):
        return N * x ** -a

    def fit_conv_landau_to_data(self, x, y, p0=(1e4 / .32, 3.38 / 5000, 1)):
        x_symm = np.linspace(-RANGE_MAX, RANGE_MAX, N_BINS * 2 + 1)
        y_symm = np.interp(x_symm, x, y)
        popt = optimize.fmin(self.scintillator.residuals, p0,
                             (x_symm, y_symm, 4500, 5500))
        return popt

    def fit_complete(self, x, y, p_gamma, p_landau):
        x_symm = np.linspace(-RANGE_MAX, RANGE_MAX, N_BINS * 2 + 1)
        y_symm = np.interp(x_symm, x, y)
        p0 = list(p_gamma) + list(p_landau)
        popt = optimize.fmin(self.complete_residuals, p0,
                             (self.scintillator, x_symm, y_symm, 500, 6000),
                             maxfun=100000)
        return popt[:2], popt[2:]

    def complete_residuals(self, par, scintillator, x, y, a, b):
        landaus = scintillator.conv_landau(x, *par[2:])
        gammas = self.gamma_func(x, *par[:2])
        residuals = (y - (gammas + landaus)) ** 2
        residuals = residuals.compress((a <= x) & (x < b))
        residuals = residuals.sum()
        return residuals


if __name__ == '__main__':
    np.seterr(invalid='ignore', divide='ignore')

    if 'data' not in globals():
        data = tables.openFile('kascade.h5', 'r')

    efficiency = ReconstructionEfficiency(data)
    efficiency.main()
