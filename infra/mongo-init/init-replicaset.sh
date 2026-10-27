#!/bin/bash
# MongoDB replica set initialisation — runs once on first boot

set -e

mongosh --quiet <<'EOF'
rs.initiate({
  _id: "emrp-rs",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 1 }
  ]
});

// Wait for primary election
let status;
let attempts = 0;
do {
  sleep(1000);
  status = rs.status();
  attempts++;
} while (!status.members.some(m => m.stateStr === "PRIMARY") && attempts < 30);

print("Replica set ready. Primary elected.");
EOF
