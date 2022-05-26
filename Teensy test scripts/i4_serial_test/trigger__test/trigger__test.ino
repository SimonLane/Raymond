void setup() {
  pinMode(29,OUTPUT);
  pinMode(30,OUTPUT);
}

void loop() {
  delay(1000);
  digitalWrite(30,1);
  delay(1000);
  digitalWrite(30,0);

}
