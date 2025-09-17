const { Client, PrivateKey } = require("@hashgraph/sdk");
require('dotenv').config();

// Configuration pour Hedera Testnet avec les clés du Developer Portal
const operatorId = process.env.HEDERA_OPERATOR_ID;
const operatorKey = process.env.HEDERA_OPERATOR_PRIVATE_KEY;

if (!operatorId || !operatorKey) {
  console.error("❌ Variables d'environnement manquantes!");
  console.error("Assurez-vous d'avoir défini HEDERA_OPERATOR_ID et HEDERA_OPERATOR_PRIVATE_KEY");
  process.exit(1);
}

// Créer le client Hedera
const client = Client.forTestnet();
client.setOperator(operatorId, operatorKey);

console.log("✅ Client Hedera configuré avec:");
console.log("   Account ID:", operatorId);
console.log("   Network: Testnet");

module.exports = { client };