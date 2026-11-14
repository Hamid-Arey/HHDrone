import types
import unittest
from unittest.mock import MagicMock, patch

from pd_controller import HardwarePWMServo, PassiveSweepController
import MAIN_FINAL


class HardwarePWMTests(unittest.TestCase):
    def test_channels_frequency_and_pulse_widths(self):
        backend = types.ModuleType('rpi_hardware_pwm')
        backend.HardwarePWM = MagicMock(side_effect=lambda **kwargs: MagicMock())
        with patch.dict('sys.modules', {'rpi_hardware_pwm': backend}):
            for pin, channel in [('GPIO12', 0), ('GPIO13', 1)]:
                servo = HardwarePWMServo(pin)
                backend.HardwarePWM.assert_called_with(pwm_channel=channel, hz=50, chip=0)
                # Each construction returns an independent channel object.
                pwm = servo._pwm
                pwm.start.assert_called_once_with(7.5)
                for angle, duty in [(-90, 5), (0, 7.5), (90, 10)]:
                    servo.angle = angle
                    pwm.change_duty_cycle.assert_called_with(duty)
                    self.assertEqual(servo.angle, angle)
                for bad in [-91, 91, float('nan')]:
                    with self.assertRaises(ValueError):
                        servo.angle = bad
                servo.close()
                servo.close()
                pwm.stop.assert_called_once_with()

    def test_rejects_incompatible_pins_before_starting(self):
        with self.assertRaisesRegex(ValueError, 'header pins 32/33'):
            HardwarePWMServo('BOARD13')
        with patch('pd_controller.HardwarePWMServo') as servo:
            with self.assertRaises(ValueError):
                PassiveSweepController('BOARD12', 'BOARD13')
            servo.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'Hardware PWM'):
            MAIN_FINAL.run(pin_numbering='physical')

    def test_stops_pan_if_tilt_start_fails(self):
        pan = MagicMock()
        with patch('pd_controller.HardwarePWMServo', side_effect=[pan, OSError('failed')]):
            with self.assertRaises(OSError):
                PassiveSweepController('GPIO12', 'GPIO13')
        pan.close.assert_called_once_with()

    def test_stops_channel_if_start_fails(self):
        pwm = MagicMock()
        pwm.start.side_effect = OSError('failed')
        backend = types.ModuleType('rpi_hardware_pwm')
        backend.HardwarePWM = MagicMock(return_value=pwm)
        with patch.dict('sys.modules', {'rpi_hardware_pwm': backend}):
            with self.assertRaises(OSError):
                HardwarePWMServo('GPIO12')
        pwm.stop.assert_called_once_with()
