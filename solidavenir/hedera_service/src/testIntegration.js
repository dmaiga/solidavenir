const {
  AccountId,
  PrivateKey,
  Client,
  AccountCreateTransaction,
  Hbar
} = require("@hashgraph/sdk");

async function testIntegration() {
  console.log("🧪 Test d'intégration Hedera SDK...");
  
  try {
    // Configuration avec vos credentials
    const MY_ACCOUNT_ID = AccountId.fromString("0.0.6808286");
    const MY_PRIVATE_KEY = PrivateKey.fromStringECDSA("cf8817834f25de2bebaea71071a4fb9be003f672b2a2600c88dc6de84d5b46a8");

    // Configurer le client
    const client = Client.forTestnet();
    client.setOperator(MY_ACCOUNT_ID, MY_PRIVATE_KEY);

    console.log("✅ Client configuré avec:", MY_ACCOUNT_ID.toString());

    // Test de création de compte
    const accountPrivateKey = PrivateKey.generateECDSA();
    const txCreateAccount = new AccountCreateTransaction()
      .setKey(accountPrivateKey.publicKey)
      .setInitialBalance(new Hbar(1)); // 1 HBAR pour les tests

    const txResponse = await txCreateAccount.execute(client);
    const receipt = await txResponse.getReceipt(client);
    const newAccountId = receipt.accountId;

    console.log("✅ Nouveau compte créé:", newAccountId.toString());
    console.log("🔑 Clé privée:", accountPrivateKey.toString());
    console.log("📋 Transaction:", txResponse.transactionId.toString());
    console.log("🔗 Hashscan: https://hashscan.io/testnet/tx/" + txResponse.transactionId.toString());

    // Test de solde
    const balance = await new AccountBalanceQuery()
      .setAccountId(newAccountId)
      .execute(client);

    console.log("💰 Solde du nouveau compte:", balance.hbars.toString(), "HBAR");

    return {
      success: true,
      accountId: newAccountId.toString(),
      privateKey: accountPrivateKey.toString()
    };

  } catch (error) {
    console.error("❌ Erreur:", error.message);
    return { success: false, error: error.message };
  }
}

// Exécuter le test si ce fichier est appelé directement
if (require.main === module) {
  testIntegration().then(result => {
    if (result.success) {
      console.log("🎉 Test d'intégration réussi!");
    } else {
      console.log("💥 Test d'intégration échoué");
      process.exit(1);
    }
  });
}

module.exports = { testIntegration };