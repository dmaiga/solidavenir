const express = require('express');
const {
  AccountId,
  PrivateKey,
  Client,
  AccountCreateTransaction,
  Hbar,
  TransferTransaction,
  AccountBalanceQuery
} = require("@hashgraph/sdk");

const app = express();
app.use(express.json());

// Configuration - Utilisez vos variables d'environnement
const MY_ACCOUNT_ID = AccountId.fromString(process.env.HEDERA_OPERATOR_ID || "0.0.6808286");
const MY_PRIVATE_KEY = PrivateKey.fromStringECDSA(process.env.HEDERA_OPERATOR_PRIVATE_KEY || "cf8817834f25de2bebaea71071a4fb9be003f672b2a2600c88dc6de84d5b46a8");

// Initialiser le client Hedera
const client = Client.forTestnet();
client.setOperator(MY_ACCOUNT_ID, MY_PRIVATE_KEY);

// Route pour créer un wallet
app.post('/create-wallet', async (req, res) => {
  try {
    const { initialBalance = 100 } = req.body;

    // Générer une nouvelle paire de clés
    const accountPrivateKey = PrivateKey.generateECDSA();
    const accountPublicKey = accountPrivateKey.publicKey;
    
    // Créer la transaction de création de compte
    const txCreateAccount = new AccountCreateTransaction()
  .setKey(accountPublicKey)
  .setInitialBalance(new Hbar(initialBalance));

const txCreateAccountResponse = await txCreateAccount.execute(client);
const receiptCreateAccountTx = await txCreateAccountResponse.getReceipt(client);
const accountId = receiptCreateAccountTx.accountId;

res.json({
  success: true,
  accountId: accountId.toString(),
  privateKey: accountPrivateKey.toString(),
  publicKey: accountPublicKey.toString(),
  transactionId: txCreateAccountResponse.transactionId.toString(),
  status: receiptCreateAccountTx.status.toString(),
  hashscanUrl: `https://hashscan.io/testnet/tx/${txCreateAccountResponse.transactionId.toString()}`
});


  } catch (error) {
    console.error("Erreur création wallet:", error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Route pour effectuer un transfert
app.post('/transfer', async (req, res) => {
  try {
    const { fromAccountId, fromPrivateKey, toAccountId, amount } = req.body;

    // Créer la transaction de transfert
    const txTransfer = new TransferTransaction()
      .addHbarTransfer(fromAccountId, new Hbar(-amount))
      .addHbarTransfer(toAccountId, new Hbar(amount))
      .freezeWith(client);
    // Signer avec la clé privée de l'expéditeur
    const signedTx = await txTransfer.sign(PrivateKey.fromStringECDSA(fromPrivateKey));
    
    // Exécuter la transaction
    const txTransferResponse = await signedTx.execute(client);
    const receiptTransferTx = await txTransferResponse.getReceipt(client);

    res.json({
      success: true,
      transactionId: txTransferResponse.transactionId.toString(),
      status: receiptTransferTx.status.toString(),
      hashscanUrl: `https://hashscan.io/testnet/tx/${txTransferResponse.transactionId.toString()}`
    });

  } catch (error) {
    console.error("Erreur transfert:", error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Route pour obtenir le solde
app.get('/balance/:accountId', async (req, res) => {
  try {
    const balance = await new AccountBalanceQuery()
      .setAccountId(req.params.accountId)
      .execute(client);
    
    res.json({
      success: true,
      balance: balance.hbars.toString()
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Route pour vérifier la santé du service
app.get('/health', async (req, res) => {
  try {
    // Test simple de connexion en obtenant le solde du compte opérateur
    const balance = await new AccountBalanceQuery()
      .setAccountId(MY_ACCOUNT_ID)
      .execute(client);
    
    res.json({
      status: 'healthy',
      operatorAccount: MY_ACCOUNT_ID.toString(),
      balance: balance.hbars.toString(),
      network: 'testnet'
    });
  } catch (error) {
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`✅ Service Hedera démarré sur le port ${PORT}`);
  console.log(`📊 Compte opérateur: ${MY_ACCOUNT_ID.toString()}`);
  console.log(`🌐 Network: Testnet`);
  console.log(`🔗 Health check: http://localhost:${PORT}/health`);
});