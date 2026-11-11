# Circuit design notes

The initial target is a unity-feedback amplifier driving 1–5 pF at 1.8 V. The current reference is 20 µA. The input and tail devices use 10/1 µm W/L; the output PMOS is 100/1 µm and the output NMOS sink is 50/1 µm. Finite device output resistance and different terminal biases mean mirror current ratios are approximate rather than exact.

The input pair produces the first voltage gain; the PMOS second stage adds gain and inverts its input, making the named `inp` terminal non-inverting overall. First-order design estimates are A0≈gm1·ro1·gm2·ro2, fu≈gm1/(2πCc), a dominant pole from Miller multiplication, an output pole associated with load capacitance, and a feed-forward zero influenced by the series compensation resistor. These estimates guide the sweep; reported values come from BSIM4 simulation, not those equations.

The AC testbench closes DC feedback using a 1 GH inductor and fixes the inverting input at AC ground through a 1 F capacitor. At the analyzed frequencies, the inductor is effectively open and the capacitor is effectively short. This gives the amplifier differential forward gain about its follower bias point. Unity-feedback phase margin is 180° plus unwrapped gain phase at the first descending unity crossing, interpolated in log frequency. It is not a general multi-loop return-ratio measurement.

Transient checks use an actual unity-connected follower, 1 ns input edges and ±100 mV steps. Settling means output stays within 1% of the commanded step amplitude until the next edge. Recorded peak dV/dt is a step-response quantity, not a claim of a fully characterized large-signal slew-rate specification.

Noise is the SPICE input-referred voltage-noise density integrated in variance over 10 Hz–10 MHz, then square-rooted. The ideal bias reference has no noise. The approximately 271 µV nominal follower error is systematic circuit offset, not a random-offset distribution. Process corner sweeps and mismatch Monte Carlo are different analyses; only the former is performed here.
