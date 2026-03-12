Lige pt skal der en del preprocessing af dataen til for overhovede at anvende programmet / hydrosieve.

Det smarte ville væer at lade programmet tage mm sieve, weight of empty sieve and weight of sieve + sample. Kig på H.3 Grain size analysis.xlsx.

So, the H.3 Grain Size Analysis.xlsx uses the columns Weight of Empty Sieve and Weight of Sieve and sample [g] to calculate weight of sample [g] (weight of sieve + sample - weight of empty sieve). Then it uses new weight of sample [g] to calculate weight in % (weight of sample [g] / weight of sieve + sample [g] * 100). Then it calculates Cum weight % (cumulative weight of sample [g] / weight of sieve + sample [g] * 100, =100-SUM(F9:F56)). Lastly, it flips this Cum weight % to get Cum weight % from 100 first to 0 last.

This new input data should be handled by the program. It ends up being the same as the old data just with the calculations already done isntead of relying on the user to do them manually to get mm sieve and cumulative weight %.
