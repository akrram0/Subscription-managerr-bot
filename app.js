let web3;

async function connectWallet() {
    if (window.ethereum) {
        web3 = new Web3(window.ethereum);
        await window.ethereum.request({ method: 'eth_requestAccounts' });
        alert("Wallet Connected");
    } else {
        alert("Install MetaMask");
    }
}

async function addSub() {
    const user = Telegram.WebApp.initDataUnsafe.user;

    await fetch("/add_subscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            user_id: user.id,
            service_name: "Netflix",
            cost: 10,
            currency: "USD",
            billing_cycle: "monthly",
            next_payment_date: "2026-03-01"
        })
    });

    alert("Subscription Added");
}
