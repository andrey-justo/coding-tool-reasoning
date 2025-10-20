// Reference implementation for Throttling using Polly
using Polly;
using Polly.Bulkhead;

class ThrottlingExample {
    public void ExecuteWithThrottling() {
        var bulkhead = Policy
            .Bulkhead(2, 4);

        for (int i = 0; i < 10; i++) {
            try {
                bulkhead.Execute(() => {
                    Console.WriteLine($"Executing task {i}");
                });
            } catch (BulkheadRejectedException ex) {
                Console.WriteLine($"Throttled: {ex.Message}");
            }
        }
    }
}
