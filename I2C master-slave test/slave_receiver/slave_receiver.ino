// Wire Slave Receiver
// by Nicholas Zambetti <http://www.zambetti.com>

// Demonstrates use of the Wire library
// Receives data as an I2C/TWI slave device
// Refer to the "Wire Master Writer" example for use with this

// Created 29 March 2006

// This example code is in the public domain.


#include <Wire.h>

int led = LED_BUILTIN;

void setup()
{
  pinMode(led, OUTPUT);
  Wire.begin(9);                // join i2c bus with address #9
  Wire.setSDA(38);
  Wire.setSCL(37);
  Wire.onReceive(receiveEvent); // register event
  Serial.begin(115200);         // start serial for output
}
long unsigned prev_t = 0;


void loop()
{
  delay(100);
  if(millis() > prev_t + 3000){
    prev_t = millis();
    Serial.println(prev_t);
  }
}

// function that executes whenever data is received from master
// this function is registered as an event, see setup()
void receiveEvent(int howMany)
{
  Serial.println("data");
  digitalWrite(led, HIGH);       // briefly flash the LED
  while(Wire.available() > 1) {  // loop through all but the last
    char c = Wire.read();        // receive byte as a character
    Serial.print(c);             // print the character
  }
  int x = Wire.read();           // receive byte as an integer
  Serial.println(x);             // print the integer
  digitalWrite(led, LOW);
}
