#include <LiquidCrystal.h>

// --- LCD Pins based on your Proteus Schematic ---
const int rs = 12, en = 11, d4 = 5, d5 = 4, d6 = 3, d7 = 2;
LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

// --- Chapter 3 Hardware Pins ---
const int relayPin = 8;     // Drives the 2N2222 Transistor
const int greenLed = 9;     // Access Granted
const int redLed = 10;      // Access Denied / Locked
const int buzzerPin = 7;    // Audio Feedback

void setup() {
  // Start Serial Communication to talk to Python via COM0COM
  Serial.begin(9600);
  
  // Setup Output Pins
  pinMode(relayPin, OUTPUT);
  pinMode(greenLed, OUTPUT);
  pinMode(redLed, OUTPUT);
  pinMode(buzzerPin, OUTPUT);
  
  // Initialize LCD and lock door
  lcd.begin(16, 2);
  lockSystem(); 
}

void loop() {
  // Check if Python has sent a signal
  if (Serial.available() > 0) {
    String receivedMessage = Serial.readStringUntil('\n');
    receivedMessage.trim(); 
    
    // --- PHASE 1: VERIFICATION COMMAND (e.g., "V,STU/2026/0001,EEG501") ---
    if (receivedMessage.startsWith("V,")) {
      int c1 = receivedMessage.indexOf(',');
      int c2 = receivedMessage.indexOf(',', c1 + 1);
      
      if (c1 > 0 && c2 > 0) {
        String matric = receivedMessage.substring(c1 + 1, c2);
        String course = receivedMessage.substring(c2 + 1);
        showVerification(matric, course);
      }
    } 
    
    // --- PHASE 2: OPEN COMMAND (e.g., "O,15") ---
    else if (receivedMessage.startsWith("O,")) {
      int c1 = receivedMessage.indexOf(',');
      if (c1 > 0) {
        String seat = receivedMessage.substring(c1 + 1);
        grantAccess(seat);
      }
    }
    
    // --- CLOSE/LOCK COMMAND ---
    else if (receivedMessage == "C") {
      lockSystem();
    }
    
    // --- HALL FULL COMMAND ---
    else if (receivedMessage == "F") {
      seatsFull();
    }
  }
}

// --- CUSTOM FUNCTIONS ---

void lockSystem() {
  digitalWrite(relayPin, LOW); // De-energize relay coil (Lock Door)
  digitalWrite(greenLed, LOW); 
  digitalWrite(redLed, HIGH);  
  
  lcd.clear();
  lcd.setCursor(0, 0); 
  lcd.print("SYSTEM LOCKED");
  lcd.setCursor(0, 1); 
  lcd.print("AWAITING SCAN...");
}

void showVerification(String matric, String course) {
  // Phase 1 Display: Show details while Python does the 2-second delay
  lcd.clear();
  lcd.setCursor(0, 0); 
  lcd.print(course); 
  lcd.setCursor(0, 1); 
  lcd.print(matric); 
}

void grantAccess(String seat) {
  // Phase 2 Display: Unlock door and assign seat
  digitalWrite(redLed, LOW);   
  digitalWrite(greenLed, HIGH); 
  
  // Happy Buzzer Beep
  tone(buzzerPin, 1000); 
  delay(200); 
  noTone(buzzerPin); 
  delay(100); 
  tone(buzzerPin, 1500); 
  delay(200); 
  noTone(buzzerPin);
  
  // Energize relay coil to spin 12V motor
  digitalWrite(relayPin, HIGH); 
  
  lcd.clear();
  lcd.setCursor(0, 0); 
  lcd.print("ACCESS GRANTED!");
  lcd.setCursor(0, 1); 
  lcd.print("SEAT NO: " + seat); 
}

void seatsFull() {
  digitalWrite(relayPin, LOW); // Ensure door is locked
  digitalWrite(greenLed, LOW); 
  digitalWrite(redLed, HIGH); 
  
  // Angry Error Beep
  tone(buzzerPin, 400); 
  delay(1000); 
  noTone(buzzerPin);
  
  lcd.clear();
  lcd.setCursor(0, 0); 
  lcd.print("ALL SEATS FULL");
  lcd.setCursor(0, 1); 
  lcd.print("WAIT FOR ADMIN");
}
