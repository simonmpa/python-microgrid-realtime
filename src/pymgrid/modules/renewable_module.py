import numpy as np
import yaml

from pymgrid.microgrid import DEFAULT_HORIZON
from pymgrid.modules.base import BaseTimeSeriesMicrogridModule


class RenewableModule(BaseTimeSeriesMicrogridModule):
    """
    A renewable energy module.

    The classic examples of renewables are photovoltaics (PV) and wind turbines.

    Parameters
    ----------
    time_series : array-like, shape (n_steps, )
        Time series of renewable production.

    forecaster : callable, float, "oracle", or None, default None.
        Function that gives a forecast n-steps ahead.

        * If ``callable``, must take as arguments ``(val_c: float, val_{c+n}: float, n: int)``, where

          * ``val_c`` is the current value in the time series: ``self.time_series[self.current_step]``

          * ``val_{c+n}`` is the value in the time series n steps in the future

          * n is the number of steps in the future at which we are forecasting.

          The output ``forecast = forecaster(val_c, val_{c+n}, n)`` must have the same sign
          as the inputs ``val_c`` and ``val_{c+n}``.

        * If ``float``, serves as a standard deviation for a mean-zero gaussian noise function
          that is added to the true value.

        * If ``"oracle"``, gives a perfect forecast.

        * If ``None``, no forecast.

    forecast_horizon : int.
        Number of steps in the future to forecast. If forecaster is None, ignored and 0 is returned.

    forecaster_increase_uncertainty : bool, default False
        Whether to increase uncertainty for farther-out dates if using a GaussianNoiseForecaster. Ignored otherwise.

    provided_energy_name: str, default "renewable_used"
        Name of the energy provided by this module, to be used in logging.

    normalized_action_bounds : tuple of int or float, default (0, 1).
        Bounds of normalized actions.
        Change to (-1, 1) for e.g. an RL policy with a Tanh output activation.

    raise_errors : bool, default False
        Whether to raise errors if bounds are exceeded in an action.
        If False, actions are clipped to the limit possible.

    """

    module_type = ("renewable", "flex")
    yaml_tag = "!RenewableModule"
    yaml_loader = yaml.SafeLoader
    yaml_dumper = yaml.SafeDumper

    state_components = np.array(["renewable"], dtype=object)

    def __init__(
        self,
        time_series,
        raise_errors=False,
        forecaster=None,
        forecast_horizon=DEFAULT_HORIZON,
        forecaster_increase_uncertainty=False,
        forecaster_relative_noise=False,
        initial_step=0,
        final_step=-1,
        normalized_action_bounds=(0, 1),
        provided_energy_name="renewable_used",
    ):
        super().__init__(
            time_series,
            raise_errors,
            forecaster=forecaster,
            forecast_horizon=forecast_horizon,
            forecaster_increase_uncertainty=forecaster_increase_uncertainty,
            forecaster_relative_noise=forecaster_relative_noise,
            initial_step=initial_step,
            final_step=final_step,
            normalized_action_bounds=normalized_action_bounds,
            provided_energy_name=provided_energy_name,
            absorbed_energy_name=None,
        )

    def update(self, external_energy_change, as_source=False, as_sink=False):
        assert (
            as_source
        ), f"Class {self.__class__.__name__} can only be used as a source."
        assert (
            external_energy_change <= self.current_renewable
        ), f"Cannot provide more than {self.current_renewable}"

        info = {
            "provided_energy": external_energy_change,
            "curtailment": self.current_renewable - external_energy_change,
        }

        return 0.0, self._done(), info

    @property
    def max_production(self):
        return self.current_renewable

    @property
    def current_renewable(self):
        """
        Current renewable production.

        Returns
        -------
        renewable : float
            Renewable production.

        """
        # print(self._time_series[self._current_step].item(), "Current step: ", self._current_step)
        return self._time_series[self._current_step].item()

    @property
    def is_source(self):
        return True
