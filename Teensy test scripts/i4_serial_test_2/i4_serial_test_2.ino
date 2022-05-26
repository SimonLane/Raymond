void setup() {
  Serial.begin(115200);
  Serial1.begin(38400);

}

void loop() {
  delay(1000);
  Serial1.write("Start");
  

}
