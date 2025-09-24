const { AccountCreateTransaction, PrivateKey, Hbar } = require("@hashgraph/sdk");
const { client } = require('./config');

class WalletService {
  // Créer un nouveau compte/wallet automatiquement
  async createWallet(initialBalance = 0) {
    try {
      // Générer une nouvelle paire de clés
      const newPrivateKey = PrivateKey.generate();
      const newPublicKey = newPrivateKey.publicKey;
      
      // Créer la transaction de création de compte
      const transaction = new AccountCreateTransaction()
        .setKey(newPublicKey)
        .setInitialBalance(new Hbar(initialBalance));
      
      // Exécuter la transaction
      const transactionResponse = await transaction.execute(client);
      
      // Obtenir le reçu contenant le nouvel ID de compte
      const receipt = await transactionResponse.getReceipt(client);
      const newAccountId = receipt.accountId;
      
      return {
        success: true,
        accountId: newAccountId.toString(),
        privateKey: newPrivateKey.toString(),
        publicKey: newPublicKey.toString()
      };
    } catch (error) {
      console.error("Erreur création wallet:", error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  // Vérifier si un compte existe et obtenir son solde
  async checkAccount(accountId) {
    try {
      const { AccountBalanceQuery } = require("@hashgraph/sdk");
      const balance = await new AccountBalanceQuery()
        .setAccountId(accountId)
        .execute(client);
      
      return {
        exists: true,
        balance: balance.hbars.toString()
      };
    } catch (error) {
      if (error.message.includes("ACCOUNT_ID_DOES_NOT_EXIST")) {
        return { exists: false };
      }
      throw error;
    }
  }
}

module.exports = new WalletService();