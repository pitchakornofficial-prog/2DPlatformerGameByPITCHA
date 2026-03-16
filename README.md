# 🎮 2D Platformer: OOP Final Project
**รายวิชา:** 1145105-68 การเขียนโปรแกรมเชิงวัตถุ (Object-Oriented Programming)
**ประเภทโครงงาน:** โครงงานเดี่ยว

---

## 👥 ข้อมูลสมาชิก (Team Members)
*   **ชื่อทีม:** ฝันร้าย OOP
*   **สมาชิก:** 1.นายพิชชากร คำพรม รหัสประจำตัว 68114540429

---

## 🚀 รายละเอียดโปรเจกต์ (Project Overview)
โปรเจกต์นี้เป็นเกมแนว **2D Action Platformer** ที่พัฒนาด้วยภาษา Python โดยใช้ไลบรารี **Pygame-CE** โครงสร้างโปรแกรมถูกออกแบบโดยอิงตามหลักการ **OOP (Object-Oriented Programming)** และ **SOLID Principles** อย่างเคร่งครัด เพื่อให้โค้ดมีความยืดหยุ่น ยืดขยายได้ง่าย (Scalability) และง่ายต่อการบำรุงรักษา

### ฟีเจอร์หลัก (Key Features)
*   **Dynamic Combo Combat System**: ระบบการต่อสู้ 3 จังหวะ พร้อมแอนิเมชันที่ลื่นไหล
*   **Advanced AI Wizard Entity**: ศัตรูที่มี State Machine (Roam, Chase, Return)
*   **Warp Portal System**: ระบบเคลื่อนย้ายมวลสารระหว่างจุดในด่าน
*   **Interactive Chest System**: การสุ่มไอเทม (Loot Table) พร้อมแอนิเมชันการเปิดแบบ Real-time
*   **Multi-layered Parallax Background**: ฉากหลังหลายระดับที่ให้ความรู้สึกมีมิติ
*   **Built-in Level Editor**: เครื่องมือสร้างด่านที่ใช้ระบบ Layer และรองรับการบันทึก/โหลดไฟล์ JSON

---

## 🏗️ การประยุกต์ใช้หลักการ OOP และ SOLID

### 1. Object-Oriented Programming (OOP)
*   **Encapsulation (การห่อหุ้ม):**
    *   คลาส `Player`, `Enemy`, และ `Chest` เก็บสถานะ (HP, Position, State) และพฤติกรรม (Update, Draw) ไว้ภายในตัวเองอย่างเป็นสัดส่วน
*   **Composition (การประกอบ):**
    *   `GameMap` ประกอบด้วย Object จากคลาส `Chest` และ `Enemy` โดยจัดการผ่านการอ่านข้อมูลจาก JSON
    *   `Player` ใช้งาน `SoundBank` และ `PlayerAnimationBank` ในการจัดการทรัพยากรเสียงและแอนิเมชัน
*   **Polymorphism (การพหุสัณฐาน):**
    *   การใช้ Duck Typing ในลูปหลักของเกม (Game Loop) ที่เรียกใช้เมธอด `.update()` และ `.draw()` ของอ็อบเจกต์ต่างประเภทกันได้อย่างอิสระ

### 2. SOLID Principles
*   **Single Responsibility Principle (SRP):**
    *   `SoundBank`: รับผิดชอบเฉพาะการโหลดและจัดการไฟล์เสียง
    *   `TileBank`: รับผิดชอบเฉพาะการจัดการ Asset รูปภาพและ Tileset
    *   `Particle`: จัดการเฉพาะ Logic ของระบบอนุภาค (Visual Effects)
*   **Open/Closed Principle (OCP):**
    *   ระบบ `GameMap` ออกแบบมาให้รองรับการเพิ่ม Layer หรือประเภท Entity ใหม่ๆ ได้ผ่านไฟล์ JSON โดยไม่ต้องแก้ไข Code หลักของ Map Rendering
*   **Liskov Substitution Principle (LSP):**
    *   คลาส Entity ต่างๆ ถูกออกแบบให้มี Interface พื้นฐานที่สอดคล้องกัน ทำให้สามารถใช้งานแทนที่กันได้ในระบบจัดการ Entity

### 3. Design Patterns
*   **Resource Bank / Flyweight:** ใช้ `TileBank` และ `AnimationBank` เพื่อโหลดครั้งเดียวและแชร์การใช้งานอ็อบเจกต์ร่วมกัน (ลดการใช้ Memory)
*   **State Pattern:** จัดการพฤติกรรมตัวละครผ่านตัวแปรสถานะ (idle, walk, jump, attack, death) ทำให้ Logic การเปลี่ยนแอนิเมชันไม่ซับซ้อน

---

## 🛠️ วิธีการติดตั้งและใช้งาน (Installation & Setup)

### 📋 สิ่งที่ต้องมีก่อน (Prerequisites)
*   Python 3.12 ขึ้นไป
*   [uv](https://github.com/astral-sh/uv) (แนะนำสำหรับการรันโปรเจกต์) หรือ pip

### ⚙️ ขั้นตอนการติดตั้ง
1.  **Clone โปรเจกต์จาก Repository**
    ```bash
    git clone https://github.com/pitchakornofficial-prog/2DPlatformerGameByPITCHA.git
    cd 2DPlatformerGameByPITCHA
    ```
2.  **ติดตั้ง Library ที่เกี่ยวข้อง**
    ```bash
    pip install -r requirements.txt
    ```
    *หรือหากใช้ uv:*
    ```bash
    uv sync
    ```

### 🎮 การเริ่มเล่นเกม
*   **รันตัวเกมหลัก:**
    ```bash
    uv run main.py
    ```
*   **รันตัวสร้างด่าน (Level Editor):**
    ```bash
    uv run levels_editor.py
    ```

---

## 🎮 การควบคุม (Controls)
*   **W, A, S, D / Arrow Keys**: เคลื่อนที่และกระโดด
*   **คลิกซ้าย (Mouse Left)**: โจมตีคอมโบ
*   **คลิกขวา (Mouse Right)**: ป้องกัน (Defend)
*   **E (Hold)**: มีปฏิสัมพันธ์กับวัตถุ (เปิดกล่อง / วาร์พ)
*   **R**: เริ่มใหม่ (Restart) เมื่อพ่ายแพ้

---

## 📖 คำอธิบายโค้ด (Code Explanation)

### 1. `main.py` (แกนหลักของเกม)
ไฟล์นี้ทำหน้าที่เป็นจุดเริ่มต้นและจัดการ Logic ทั้งหมดของเกม:
*   **โครงสร้างคลาส**: ออกแบบโดยใช้คลาสเพื่อแยกแยะหน้าที่ชัดเจน เช่น `Player`, `Enemy`, `Chest`, และ `GameMap`
*   **การจัดการทรัพยากร**:
    *   `SoundBank`: โหลดและแคชเสียงเอฟเฟกต์ เพื่อลดการอ่านไฟล์ซ้ำซ้อน
    *   `PlayerAnimationBank` & `TileBank`: จัดการสไปรท์แอนิเมชันและแผ่นกระเบื้อง (Tileset)
*   **ตัวละครและศัตรู**:
    *   `Player`: ควบคุมฟิสิกส์ (Gravity/Collision) และระบบ Combo Attack
    *   `Enemy (Portal Wizard)`: มี AI แบบ State Machine จัดการสถานะการเดินลาดตระเวน (Roam), ไล่ตาม (Chase) และกลับจุดเกิด (Return)
*   **ระบบแผนที่**: คลาส `GameMap` จัดการการแสดงผลแบบ Layer และ Parallax Background เพื่อความสวยงาม

### 2. `levels_editor.py` (เครื่องมือสร้างด่าน)
เครื่องมือที่ช่วยให้การออกแบบด่านทำได้ง่ายขึ้น:
*   **ระบบ UI**: มี Panel จัดการไฟล์ (New/Save/Load) และเลือกเครื่องมือต่างๆ
*   **การควบคุม**: รองรับการซูม (Zoom) และเลื่อน (Scroll) แผนที่ขนาดใหญ่
*   **ฟังก์ชันการแก้ไข**:
    *   **Layer System**: เลือกวาดได้ถึง 8 เลเยอร์ (พื้นหลัง, พื้นผิว, วัตถุ, ศัตรู)
    *   **Entity Config**: ตั้งค่า HP ศัตรู, ไอเทมในกล่อง, และตำแหน่งจุดวาร์พได้ทันที
*   **การเก็บข้อมูล**: บันทึกข้อมูลด่านในรูปแบบไฟล์ JSON ที่ `main.py` สามารถอ่านไปใช้งานได้โดยตรง

---
**โครงงานนี้เป็นส่วนหนึ่งของวิชา OOP Final Project - 2026**
