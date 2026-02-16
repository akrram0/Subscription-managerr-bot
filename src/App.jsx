import { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import WebApp from '@twa-dev/sdk';
import './App.css';

// عنوان محفظة البوت (المستقبل)
const RECEIVER_ADDRESS = "0xYOUR_WALLET_ADDRESS_HERE"; 
const SUBSCRIPTION_PRICE = "0.001"; // السعر بعملة ETH/BNB/MATIC

function App() {
  const [account, setAccount] = useState(null);
  const [lang, setLang] = useState('en');

  useEffect(() => {
    // تفعيل تطبيق تلغرام وتحديد اللغة
    WebApp.ready();
    WebApp.expand();
    if (WebApp.initDataUnsafe.user?.language_code === 'ar') {
      setLang('ar');
    }
  }, []);

  const connectWallet = async () => {
    if (window.ethereum) {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await provider.send("eth_requestAccounts", []);
      setAccount(accounts[0]);
    } else {
      alert(lang === 'ar' ? "يرجى تثبيت محفظة (مثل MetaMask)" : "Please install a wallet");
    }
  };

  const paySubscription = async () => {
    if (!account) return;
    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const signer = await provider.getSigner();
      
      const tx = await signer.sendTransaction({
        to: RECEIVER_ADDRESS,
        value: ethers.parseEther(SUBSCRIPTION_PRICE)
      });

      alert(lang === 'ar' ? "تم إرسال المعاملة!" : "Transaction Sent!");
      
      // إبلاغ البوت بالدفع
      await fetch('https://your-bot-api-url.com/verify-payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: WebApp.initDataUnsafe.user?.id,
          txHash: tx.hash
        })
      });

      WebApp.close(); // إغلاق التطبيق بعد النجاح

    } catch (error) {
      console.error(error);
      alert("Payment Failed");
    }
  };

  const t = {
    ar: { title: "إدارة الاشتراك", connect: "ربط المحفظة", pay: "دفع الاشتراك" },
    en: { title: "Subscription Manager", connect: "Connect Wallet", pay: "Pay Subscription" }
  };

  return (
    <div className="container">
      <h1>{t[lang].title}</h1>
      {!account ? (
        <button onClick={connectWallet}>{t[lang].connect}</button>
      ) : (
        <div>
          <p>Wallet: {account.slice(0, 6)}...{account.slice(-4)}</p>
          <button className="pay-btn" onClick={paySubscription}>
            {t[lang].pay} ({SUBSCRIPTION_PRICE} ETH)
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
