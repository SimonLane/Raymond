void setup() {
  Serial.begin(115200); 
  Serial1.begin(38400, SERIAL_8N1);
//  pinMode(0,OUTPUT);
//  pinMode(1,OUTPUT);
}
String rc = "";

void loop() {
  Serial.println("-");
  delay(1000);
  Serial1.print("Start");
  delay(10);

  while (Serial1.available()) {
    Serial.write(Serial1.read());
  }
}
