# Run failed

```
Traceback (most recent call last):
  File "/home/runner/work/signal-desk/signal-desk/conf_research.py", line 374, in <module>
    main()
  File "/home/runner/work/signal-desk/signal-desk/conf_research.py", line 275, in main
    um = hourly("UMAC")
         ^^^^^^^^^^^^^^
  File "/home/runner/work/signal-desk/signal-desk/conf_research.py", line 53, in hourly
    raise RuntimeError(f"no hourly data for {ticker}")
RuntimeError: no hourly data for UMAC
```
