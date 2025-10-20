// Reference implementation for Sharding/Partitioning using Entity Framework Core
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;

class ShardingDbContext : DbContext {
    public DbSet<Customer> Customers { get; set; }
    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder) {
        // Example: Partition by region
        string region = "US"; // This could be dynamic
        string connectionString = region == "US" ? "USConnectionString" : "EUConnectionString";
        optionsBuilder.UseSqlServer(connectionString);
    }
}

class Customer {
    public int Id { get; set; }
    public string Name { get; set; }
}
