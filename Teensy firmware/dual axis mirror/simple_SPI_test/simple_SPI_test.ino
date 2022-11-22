

// include the SPI library:
#include <SPI.h>


// set pin 10 as the slave select for the digital pot:
const int slaveSelectPin = 10;
const int slaveReadyPin = 35;
const int trigger_pin = 34;


void setup() {
  Serial.begin(115200);
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (trigger_pin, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (slaveReadyPin, INPUT);
  digitalWrite (slaveSelectPin, HIGH);
  SPI.begin(); 
  delay(1000);

// input stage
  sendWriteSPI(0x40005102,0x61,0x61);                                   //Select signal generator system as active input for X and static value for Y axis.
  sendWriteSPI(0x60006001,0x02,0x01);                                   //(XY units, run_flag:true) [Units: 0,Current; 1,Optical feedback; 2,XY]
  sendWriteSPI(0x60026003,0x01,generateSPFPR(1.5));                    //(shape, Hz)[shape: 0,sine; 1,Triangle; 2, Square; 3,Saw; 4, Pulse]
  sendWriteSPI(0x60046005,generateSPFPR(0.8),generateSPFPR(0));         //(Amplitude, Offset)
  sendWriteSPI(0x60066007,generateSPFPR(0),1);                          //(Phase [radians], Cycles [-1 for infinite])
  sendWriteSPI(0x60086009,generateSPFPR(0.5),1);                        //(Duty cycle, Ext trig)

//input conditioning
  sendWriteSPI(0x98009801,generateSPFPR(0.05),generateSPFPR(0.033));      // X  (Gain, Offset)
  sendWriteSPI(0x99009901,generateSPFPR(0.05),generateSPFPR(0.047));      // Y  (Gain, Offset)

//control stage (open or closed loop)
  //sendWriteSPI(0x40024007,0xC0,0xC0);       //Activate closed loop control for both axes

// output conditioning
      //leave all as default
// Output stage
      //leave all as default
}


float z = 0.25;

void loop() {

  z=z-0.05;
  if(z<-0.25){z=0.25;}
  sendWriteSPI(0x51025102,generateSPFPR(z),generateSPFPR(z));
  delay(1500);
  //trigger pin
  digitalWrite(trigger_pin,1);
  delay(1);
  digitalWrite(trigger_pin,0);
}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){

  while(digitalRead(slaveReadyPin) == HIGH){}//wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);     //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}    //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer(valueX >> i & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer(valueY >> i & 0xFF);}         //Y command
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  if(true){ //printout 
    Serial.print("SPI transfer: ");
    Serial.print(registers, HEX);Serial.print(valueX, HEX);Serial.println(valueY, HEX);
  }
}


uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0) 
    return 0; //handle this special case
  //check sign and begin normalization
  if (f < 0) { 
    sign = 1; 
    normalized = -f; 
  } else { 
    sign = 0; 
    normalized = f; 
  }
  //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { 
    normalized /= 2.0; 
    shift++; 
  }
  while (normalized < 1.0) { 
    normalized *= 2.0; 
    shift--; 
  }
  normalized = normalized - 1.0;
  //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
  //get biased exponent
  exponent = shift + 0x7f; //shift + bias
  //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}
