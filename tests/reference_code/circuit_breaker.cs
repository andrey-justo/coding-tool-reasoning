// Reference implementation for Circuit Breaker using Polly
using Polly;
using Polly.CircuitBreaker;

class CircuitBreakerExample {
    public void ExecuteWithCircuitBreaker() {
        var circuitBreaker = Policy
            .Handle<Exception>()
            .CircuitBreaker(2, TimeSpan.FromMinutes(1));

        try {
            circuitBreaker.Execute(() => {
                // Simulate operation that may fail
                Console.WriteLine("Executing protected code");
                throw new Exception("Failure");
            });
        } catch (BrokenCircuitException ex) {
            Console.WriteLine($"Circuit is open: {ex.Message}");
        }
    }
}
