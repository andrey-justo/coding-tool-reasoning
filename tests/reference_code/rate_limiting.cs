// Reference implementation for Rate Limiting using Polly
using Polly;
using Polly.RateLimit;

class RateLimitingExample {
    public void ExecuteWithRateLimit() {
        var rateLimiter = Policy
            .RateLimit(5, TimeSpan.FromSeconds(10));

        for (int i = 0; i < 10; i++) {
            try {
                rateLimiter.Execute(() => {
                    Console.WriteLine($"Request {i} allowed");
                });
            } catch (RateLimitRejectedException ex) {
                Console.WriteLine($"Rate limit exceeded: {ex.Message}");
            }
        }
    }
}
