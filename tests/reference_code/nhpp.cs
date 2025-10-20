// Reference implementation for Non-Homogeneous Poisson Process (NHPP) using Math.NET Numerics
using MathNet.Numerics.Distributions;
using System;

class NHPPExample {
    public void SimulateNHPP() {
        // Example: Simulate Poisson arrivals with time-varying rate
        double[] rates = { 2.0, 5.0, 3.0 }; // rates for different intervals
        int[] arrivals = new int[rates.Length];
        for (int i = 0; i < rates.Length; i++) {
            arrivals[i] = Poisson.Sample(rates[i]);
            Console.WriteLine($"Interval {i}: {arrivals[i]} arrivals");
        }
    }
}
