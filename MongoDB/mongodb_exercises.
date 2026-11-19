// ============================================================================
// CHƯƠNG 1: DOCUMENT STORE (MONGODB) - THỰC HÀNH & BÀI TẬP (mongosh)
// Chạy bằng: docker compose -f compose.yaml exec -T mongo mongosh < mongodb_exercises.js
// ============================================================================

use("shop");

// Dọn sạch collection trước khi chạy lại
db.orders.drop();
db.orders_bench.drop();

// ----------------------------------------------------------------------------
// PHẦN 1: THỰC HÀNH CRUD CƠ BẢN (THEO BÀI HỌC)
// ----------------------------------------------------------------------------
print("\n=== 1. INSERT DOCUMENTS ===");
db.orders.insertOne({
  _id: 1001,
  customer: { name: "Linh", city: "Hanoi" },
  status: "paid",
  items: [
    { sku: "BK-01", title: "Python Basics", qty: 2, price: 12.5 },
    { sku: "BK-07", title: "SQL in Practice", qty: 1, price: 18.0 },
  ],
  tags: ["student", "first-order"]
});

db.orders.insertMany([
  {
    _id: 1002,
    customer: { name: "Nam", city: "Da Nang" },
    status: "shipped",
    items: [{ sku: "BK-03", title: "Data Viz", qty: 1, price: 22.0 }]
  },
  {
    _id: 1003,
    customer: { name: "Mai", city: "Hanoi" },
    status: "paid",
    items: [{ sku: "BK-01", title: "Python Basics", qty: 1, price: 12.5 }],
    coupon: "WELCOME10"
  }
]);

// ----------------------------------------------------------------------------
// BÀI TẬP 1: Thêm 5 đơn hàng có hình dạng khác nhau, rồi tìm mọi đơn chứa một sku cho trước
// ----------------------------------------------------------------------------
print("\n=== BÀI TẬP 1: THÊM 5 ĐƠN HÀNG ĐA DẠNG SCHEMA & TÌM THEO SKU ===");
db.orders.insertMany([
  {
    _id: 1004,
    customer: { name: "Hung", city: "Hue", tier: "gold" },
    status: "paid",
    items: [
      { sku: "BK-01", title: "Python Basics", qty: 3, price: 12.5 },
      { sku: "BK-09", title: "MongoDB Guide", qty: 1, price: 25.0 }
    ],
    note: "Giao giờ hành chính"
  },
  {
    _id: 1005,
    customer: { name: "An", city: "HCMC", phone: "0901234567" },
    status: "shipped",
    items: [{ sku: "BK-05", title: "Graph Databases", qty: 2, price: 30.0 }],
    giftWrap: true
  },
  {
    _id: 1006,
    customer: { name: "Binh", city: "Hanoi" },
    status: "pending",
    items: [
      { sku: "BK-03", title: "Data Viz", qty: 1, price: 22.0 },
      { sku: "BK-01", title: "Python Basics", qty: 1, price: 12.5 }
    ],
    paymentMethod: "COD"
  },
  {
    _id: 1007,
    customer: { name: "Chi", city: "Da Nang" },
    status: "paid",
    items: [{ sku: "BK-11", title: "Cassandra Internals", qty: 1, price: 35.0 }],
    coupon: "FREESHIP",
    discount: 5.0
  },
  {
    _id: 1008,
    customer: { name: "Duc", city: "HCMC" },
    status: "shipped",
    items: [
      { sku: "BK-07", title: "SQL in Practice", qty: 2, price: 18.0 },
      { sku: "BK-09", title: "MongoDB Guide", qty: 1, price: 25.0 }
    ],
    tags: ["vip", "fast-delivery"]
  }
]);

print("Tất cả đơn hàng chứa sku 'BK-01':");
printjson(
  db.orders.find(
    { "items.sku": "BK-01" },
    { _id: 1, "customer.name": 1, "customer.city": 1, status: 1, "items.sku": 1 }
  ).sort({ _id: 1 }).toArray()
);


// ----------------------------------------------------------------------------
// BÀI TẬP 2: Viết một aggregation trả về doanh thu theo thành phố
// ----------------------------------------------------------------------------
print("\n=== BÀI TẬP 2: AGGREGATION DOANH THU THEO THÀNH PHỐ ===");
printjson(
  db.orders.aggregate([
    { $match: { status: { $in: ["paid", "shipped"] } } },
    { $unwind: "$items" },
    {
      $group: {
        _id: "$customer.city",
        totalOrders: { $addToSet: "$_id" },
        totalUnits: { $sum: "$items.qty" },
        revenue: { $sum: { $multiply: ["$items.qty", "$items.price"] } }
      }
    },
    {
      $project: {
        _id: 0,
        city: "$_id",
        orderCount: { $size: "$totalOrders" },
        totalUnits: 1,
        revenue: { $round: ["$revenue", 2] }
      }
    },
    { $sort: { revenue: -1, city: 1 } }
  ]).toArray()
);


// ----------------------------------------------------------------------------
// BÀI TẬP 3: Tạo index và so sánh explain() trước & sau trên 10.000 document
// ----------------------------------------------------------------------------
print("\n=== BÀI TẬP 3: SO SÁNH EXPLAIN() TRƯỚC VÀ SAU INDEX (10.000 DOCUMENTS) ===");
const cities = ["Hanoi", "HCMC", "Da Nang", "Hue", "Can Tho"];
const statuses = ["paid", "shipped", "pending", "cancelled"];
const bulkDocs = [];

for (let i = 1; i <= 10000; i++) {
  bulkDocs.push({
    _id: i,
    customer: {
      name: `User_${i}`,
      city: cities[i % cities.length]
    },
    status: statuses[i % statuses.length],
    amount: Number(((i % 10 + 1) * 12.5).toFixed(2))
  });
}
db.orders_bench.insertMany(bulkDocs);
print("Đã nạp: " + db.orders_bench.countDocuments() + " documents vào shop.orders_bench.");

const queryFilter = { "customer.city": "Hanoi", status: "paid" };

const beforeExplain = db.orders_bench.find(queryFilter).explain("executionStats");
print("\n--- TRƯỚC KHI TẠO INDEX ---");
printjson({
  stage: beforeExplain.executionStats.executionStages.stage,
  nReturned: beforeExplain.executionStats.nReturned,
  totalDocsExamined: beforeExplain.executionStats.totalDocsExamined,
  totalKeysExamined: beforeExplain.executionStats.totalKeysExamined,
  executionTimeMillis: beforeExplain.executionStats.executionTimeMillis
});

// Tạo Compound Index trên (customer.city, status)
db.orders_bench.createIndex({ "customer.city": 1, status: 1 });

const afterExplain = db.orders_bench.find(queryFilter).explain("executionStats");
print("\n--- SAU KHI TẠO INDEX ({ 'customer.city': 1, status: 1 }) ---");
printjson({
  stage: afterExplain.executionStats.executionStages.stage,
  inputStage: afterExplain.executionStats.executionStages.inputStage?.stage,
  nReturned: afterExplain.executionStats.nReturned,
  totalDocsExamined: afterExplain.executionStats.totalDocsExamined,
  totalKeysExamined: afterExplain.executionStats.totalKeysExamined,
  executionTimeMillis: afterExplain.executionStats.executionTimeMillis
});
