//Test script to control the glavo and the ETL at the same time. ETL controlled via analog output
// of the MCP4822 chip over SPI

#include <SPI.h>     //for analog ETL control via MCP4822

int CS = 33;
int Latch = 30;

void setup() {
  Serial.begin(115200);           
  analogWriteResolution(12);
//galvo control
  pinMode(A22,OUTPUT);  
  analogWrite(A22,2047);
//MCP control
  pinMode(CS, OUTPUT);
  pinMode(Latch, OUTPUT);
  digitalWrite(CS,1);
  digitalWrite(Latch,1);
  SPI.begin();
// (for testing output)
  pinMode(A4,INPUT); 
}

void Aout(){
  Serial.println(analogRead(A4));
}

void setValue(int v, int c, int g){ //for writing a value to the MCP register

  byte out1 = 0x50 | (c<<7)| (g<<5) | (v>>8) ;
  byte out2 = v & 0xFF ;
  //SPI.beginTransaction(SPISettings(20000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS, LOW);
  SPI.transfer(out1);
  SPI.transfer(out2);
  digitalWrite(CS, HIGH);
  digitalWrite(Latch,LOW);
  digitalWrite(Latch,HIGH);
}

// serial commands
String device = "";
String command1 = "";
String command2 = "";
String command3 = "";
int serial_part = 0;

void checkSerial() {   
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {respond(device,command1,command2); serial_part = 0;}   // ';' char
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
   else if (serial_part == 4){command3 += rc;}
 }
}

void respond(String device,String command1, String command2) {
  if(device == "hello")       {Serial.println("Hi there!");}
//galvo_calibration
    if(device == "gc")        {analogWrite(A22,(command1.toInt()));Serial.println(command1);}
    if(device == "etl")       {setValue(command1.toInt(),1,0);}
    if(device == "a")         {Aout();}
    command1= "";command2= "";command3= "";
  }
void loop() {
  checkSerial();


}
