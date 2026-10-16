# Run failed

```
Traceback (most recent call last):
  File "/home/runner/work/signal-desk/signal-desk/conf_avgo.py", line 116, in <module>
    main()
  File "/home/runner/work/signal-desk/signal-desk/conf_avgo.py", line 66, in main
    x = at(c, pd.DatetimeIndex(ln["time"] + pd.Timedelta(hours=sh)))
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/signal-desk/signal-desk/conf_avgo.py", line 49, in at
    return s.asof(times).to_numpy(float)
           ^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/generic.py", line 8242, in asof
    locs = self.index.asof_locs(where, ~nulls._values)  # type: ignore[operator]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/indexes/base.py", line 5859, in asof_locs
    locs = self._values[mask].searchsorted(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/arrays/_mixins.py", line 255, in searchsorted
    npvalue = self._validate_setitem_value(value)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/arrays/datetimelike.py", line 739, in _validate_setitem_value
    value = self._validate_listlike(value)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/arrays/datetimelike.py", line 675, in _validate_listlike
    value = value.as_unit(self.unit, round_ok=False)  # type: ignore[attr-defined]
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/arrays/datetimelike.py", line 2056, in as_unit
    new_values = astype_overflowsafe(self._ndarray, dtype, round_ok=round_ok)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "pandas/_libs/tslibs/np_datetime.pyx", line 373, in pandas._libs.tslibs.np_datetime.astype_overflowsafe
  File "pandas/_libs/tslibs/np_datetime.pyx", line 418, in pandas._libs.tslibs.np_datetime.astype_overflowsafe
  File "pandas/_libs/tslibs/np_datetime.pyx", line 588, in pandas._libs.tslibs.np_datetime._astype_overflowsafe_to_smaller_unit
ValueError: Cannot losslessly cast '1788040267704280064 ns' to s
```
