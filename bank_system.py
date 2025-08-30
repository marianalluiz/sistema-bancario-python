
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema Bancário em Python (CLI)
--------------------------------
MVP: depósito, saque e extrato
Plus: cadastro de clientes/contas, limite diário de saques, autenticação simples,
      exportação de extrato, persistência opcional em JSON.
"
Autor: Você (Mari!) — Bootcamp Santander / DIO
Licença: MIT
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import getpass
import json
import os
import hashlib

# --------------------------
# Utilidades
# --------------------------
def now() -> datetime:
    return datetime.now()

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

def money(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --------------------------
# Modelos
# --------------------------
@dataclass
class Transaction:
    kind: str                 # 'DEPOSITO' | 'SAQUE'
    amount: float
    timestamp: datetime = field(default_factory=now)
    note: str = ""

@dataclass
class Account:
    number: str
    agency: str = "0001"
    owner_cpf: str = ""
    balance: float = 0.0
    transactions: List[Transaction] = field(default_factory=list)
    daily_withdraw_limit: int = 3
    per_withdraw_limit_value: float = 500.0

    def deposit(self, amount: float, note: str = "") -> None:
        if amount <= 0:
            raise ValueError("O valor do depósito deve ser positivo.")
        self.balance += amount
        self.transactions.append(Transaction("DEPOSITO", amount, note=note))

    def withdrawals_today(self) -> int:
        today = date.today()
        return sum(1 for t in self.transactions if t.kind == "SAQUE" and t.timestamp.date() == today)

    def withdraw(self, amount: float, note: str = "") -> None:
        if amount <= 0:
            raise ValueError("O valor do saque deve ser positivo.")
        if amount > self.balance:
            raise ValueError("Saldo insuficiente.")
        if amount > self.per_withdraw_limit_value:
            raise ValueError(f"Saque acima do limite por operação ({money(self.per_withdraw_limit_value)}).")
        if self.withdrawals_today() >= self.daily_withdraw_limit:
            raise ValueError("Limite diário de saques atingido.")
        self.balance -= amount
        self.transactions.append(Transaction("SAQUE", -amount, note=note))

    def statement(self, start: Optional[date] = None, end: Optional[date] = None) -> Tuple[List[Transaction], float]:
        txs = self.transactions
        if start:
            txs = [t for t in txs if t.timestamp.date() >= start]
        if end:
            txs = [t for t in txs if t.timestamp.date() <= end]
        balance = sum(t.amount for t in txs)
        return txs, balance

@dataclass
class User:
    cpf: str
    name: str
    password_hash: str
    accounts: List[str] = field(default_factory=list)  # lista de números de conta

# --------------------------
# Banco (repositório em memória + persistência opcional)
# --------------------------
class Bank:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.accounts: Dict[str, Account] = {}

    # --------- Usuários ---------
    def create_user(self, cpf: str, name: str, password: str) -> None:
        if cpf in self.users:
            raise ValueError("Já existe um usuário com esse CPF.")
        self.users[cpf] = User(cpf=cpf, name=name, password_hash=hash_password(password))

    def auth(self, cpf: str, password: str) -> User:
        u = self.users.get(cpf)
        if not u or u.password_hash != hash_password(password):
            raise PermissionError("Credenciais inválidas.")
        return u

    # --------- Contas ---------
    def create_account(self, owner_cpf: str) -> Account:
        if owner_cpf not in self.users:
            raise ValueError("Usuário não encontrado para criar conta.")
        number = str(100000 + len(self.accounts) + 1)  # simples gerador
        acc = Account(number=number, owner_cpf=owner_cpf)
        self.accounts[number] = acc
        self.users[owner_cpf].accounts.append(number)
        return acc

    def get_account(self, number: str) -> Account:
        if number not in self.accounts:
            raise ValueError("Conta não encontrada.")
        return self.accounts[number]

    # --------- Persistência (JSON) ---------
    def save(self, path: str) -> None:
        def serialize_account(a: Account):
            return {
                "number": a.number,
                "agency": a.agency,
                "owner_cpf": a.owner_cpf,
                "balance": a.balance,
                "transactions": [
                    {"kind": t.kind, "amount": t.amount, "timestamp": t.timestamp.isoformat(), "note": t.note}
                    for t in a.transactions
                ],
                "daily_withdraw_limit": a.daily_withdraw_limit,
                "per_withdraw_limit_value": a.per_withdraw_limit_value,
            }
        data = {
            "users": {cpf: {"cpf": u.cpf, "name": u.name, "password_hash": u.password_hash, "accounts": u.accounts}
                      for cpf, u in self.users.items()},
            "accounts": {n: serialize_account(a) for n, a in self.accounts.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.users = {cpf: User(**ud) for cpf, ud in data.get("users", {}).items()}
        self.accounts = {}
        for n, ad in data.get("accounts", {}).items():
            acc = Account(
                number=ad["number"],
                agency=ad["agency"],
                owner_cpf=ad["owner_cpf"],
                balance=ad["balance"],
                daily_withdraw_limit=ad.get("daily_withdraw_limit", 3),
                per_withdraw_limit_value=ad.get("per_withdraw_limit_value", 500.0),
            )
            for t in ad["transactions"]:
                acc.transactions.append(Transaction(kind=t["kind"], amount=t["amount"],
                                                    timestamp=datetime.fromisoformat(t["timestamp"]), note=t.get("note","")))
            self.accounts[n] = acc

# --------------------------
# CLI
# --------------------------
DATA_FILE = "bank_data.json"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def pause():
    input("\nPressione Enter para continuar...")

def header(txt: str):
    print("=" * 60)
    print(txt.center(60))
    print("=" * 60)

def main():
    bank = Bank()
    bank.load(DATA_FILE)
    current_user: Optional[User] = None
    current_account: Optional[Account] = None

    while True:
        clear()
        header("SISTEMA BANCÁRIO - DIO / SANTANDER (Python)")
        if current_user:
            print(f"Usuário: {current_user.name} (CPF {current_user.cpf})")
        if current_account:
            print(f"Conta atual: Agência {current_account.agency} • Nº {current_account.number} • Saldo {money(current_account.balance)}")
        print("-" * 60)
        print("1) Criar usuário")
        print("2) Login")
        print("3) Criar conta")
        print("4) Selecionar conta")
        print("5) Depósito")
        print("6) Saque")
        print("7) Extrato")
        print("8) Exportar extrato (.txt)")
        print("9) Salvar")
        print("0) Sair")
        choice = input("\nEscolha: ").strip()

        try:
            if choice == "1":
                cpf = input("CPF (somente números): ").strip()
                name = input("Nome: ").strip()
                pwd = getpass.getpass("Crie uma senha: ")
                bank.create_user(cpf, name, pwd)
                print("✅ Usuário criado.")
                pause()
            elif choice == "2":
                cpf = input("CPF: ").strip()
                pwd = getpass.getpass("Senha: ")
                current_user = bank.auth(cpf, pwd)
                # auto-seleciona primeira conta se existir
                current_account = bank.get_account(current_user.accounts[0]) if current_user.accounts else None
                print("✅ Login efetuado.")
                pause()
            elif choice == "3":
                if not current_user:
                    print("⚠ Faça login primeiro.")
                    pause(); continue
                acc = bank.create_account(current_user.cpf)
                current_account = acc
                print(f"✅ Conta criada: Agência {acc.agency}, Nº {acc.number}")
                pause()
            elif choice == "4":
                if not current_user or not current_user.accounts:
                    print("⚠ Faça login e crie uma conta primeiro.")
                    pause(); continue
                print("Suas contas:")
                for n in current_user.accounts:
                    a = bank.get_account(n)
                    print(f"- {n} (saldo {money(a.balance)})")
                sel = input("Número da conta: ").strip()
                current_account = bank.get_account(sel)
            elif choice == "5":
                if not current_account:
                    print("⚠ Selecione uma conta primeiro.")
                    pause(); continue
                val = float(input("Valor do depósito: ").replace(",", "."))
                note = input("Observação (opcional): ")
                current_account.deposit(val, note=note)
                print(f"✅ Depósito de {money(val)} realizado.")
                pause()
            elif choice == "6":
                if not current_account:
                    print("⚠ Selecione uma conta primeiro.")
                    pause(); continue
                val = float(input("Valor do saque: ").replace(",", "."))
                note = input("Observação (opcional): ")
                current_account.withdraw(val, note=note)
                print(f"✅ Saque de {money(val)} realizado.")
                pause()
            elif choice == "7":
                if not current_account:
                    print("⚠ Selecione uma conta primeiro.")
                    pause(); continue
                print("\nEXTRATO")
                print("-" * 60)
                for t in current_account.transactions:
                    ts = t.timestamp.strftime("%d/%m/%Y %H:%M")
                    val = money(t.amount if t.kind == "DEPOSITO" else -abs(t.amount))
                    print(f"{ts}  {t.kind:<10}  {val:>15}  {t.note}")
                print("-" * 60)
                print(f"Saldo atual: {money(current_account.balance)}")
                pause()
            elif choice == "8":
                if not current_account:
                    print("⚠ Selecione uma conta primeiro.")
                    pause(); continue
                fname = f"extrato_{current_account.number}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write("EXTRATO\n")
                    f.write("="*60 + "\n")
                    for t in current_account.transactions:
                        ts = t.timestamp.strftime("%d/%m/%Y %H:%M")
                        val = money(t.amount if t.kind == "DEPOSITO" else -abs(t.amount))
                        f.write(f"{ts}  {t.kind:<10}  {val:>15}  {t.note}\n")
                    f.write("-"*60 + "\n")
                    f.write(f"Saldo atual: {money(current_account.balance)}\n")
                print(f"✅ Extrato exportado: {fname}")
                pause()
            elif choice == "9":
                bank.save(DATA_FILE)
                print("✅ Dados salvos.")
                pause()
            elif choice == "0":
                bank.save(DATA_FILE)
                print("Até logo!")
                break
            else:
                print("Opção inválida.")
                pause()
        except Exception as e:
            print(f"❌ Erro: {e}")
            pause()

if __name__ == "__main__":
    main()
