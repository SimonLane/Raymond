#define HWSERIAL Serial1


void setup() {
  Serial.begin(115200); 
  HWSERIAL.begin(115200);
//  pinMode(0,OUTPUT);
//  pinMode(1,OUTPUT);
}
String rc = "";

//void loop() {
//  Serial.println("-");
//  delay(1000);
//  HWSERIAL.println("Start");
//  delay(100);
//  rc = "-->";
//  while (HWSERIAL.available() > 0) {
//    rc += Serial.read();
//  }
//  Serial.println(rc);
//}

void loop() {
        int incomingByte;
        
  if (Serial.available() > 0) {
    incomingByte = Serial.read();
    Serial.print("USB received: ");
    Serial.println(incomingByte);
    HWSERIAL.print(incomingByte);
  }
  if (HWSERIAL.available() > 0) {
    incomingByte = HWSERIAL.read();
    Serial.print("UART received: ");
    Serial.println(incomingByte, DEC);
  }
}
